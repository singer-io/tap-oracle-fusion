from datetime import datetime
from typing import Any, Dict, Mapping, Optional

import singer
from singer import metadata

from tap_oracle_fusion.client import OracleClient
from tap_oracle_fusion.discover import get_stream_resource_map

LOGGER = singer.get_logger()


def _parse_timestamp(timestamp_value: Optional[str]) -> Optional[datetime]:
    if not timestamp_value or not isinstance(timestamp_value, str):
        return None

    normalized = timestamp_value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _state_is_valid(state: Dict[str, Any]) -> bool:
    return isinstance(state, dict) and (
        "bookmarks" not in state or isinstance(state.get("bookmarks"), dict)
    )


def update_currently_syncing(state: Dict[str, Any], stream_name: Optional[str]) -> None:
    if not stream_name and singer.get_currently_syncing(state):
        del state["currently_syncing"]
    else:
        singer.set_currently_syncing(state, stream_name)
    singer.write_state(state)


def _get_stream_meta(catalog_entry: singer.CatalogEntry) -> Dict[str, Any]:
    return metadata.to_map(catalog_entry.metadata).get((), {})


def _get_replication_key(catalog_entry: singer.CatalogEntry) -> Optional[str]:
    stream_meta = _get_stream_meta(catalog_entry)
    replication_keys = stream_meta.get("valid-replication-keys") or []
    if replication_keys:
        return replication_keys[0]
    return None


def _get_oracle_path(catalog_entry: singer.CatalogEntry) -> str:
    stream_meta = _get_stream_meta(catalog_entry)
    oracle_path = stream_meta.get("oracle-path")
    if isinstance(oracle_path, str) and oracle_path:
        return oracle_path
    return ""


def _bookmark_value(state: Dict[str, Any], stream: str, replication_key: str, start_date: str) -> str:
    return singer.get_bookmark(state, stream, replication_key, start_date)


def _write_bookmark(state: Dict[str, Any], stream: str, replication_key: str, value: str) -> Dict[str, Any]:
    return singer.write_bookmark(state, stream, replication_key, value)


def _build_incremental_query(
    replication_key: str,
    bookmark_value: str,
) -> Dict[str, Any]:
    """Build Oracle query parameter for incremental filtering."""
    query_expression = f"{replication_key}>='{bookmark_value}'"
    return {"q": query_expression}


def sync(config: Mapping[str, Any], catalog: singer.Catalog, state: Dict[str, Any]) -> None:
    if not _state_is_valid(state):
        raise RuntimeError("Invalid state format. 'bookmarks' must be an object.")

    client = OracleClient(config)
    stream_to_path = get_stream_resource_map(config)
    selected_streams = catalog.get_selected_streams(state)
    with singer.Transformer() as transformer:
        for selected_stream in selected_streams:
            catalog_entry = catalog.get_stream(selected_stream.tap_stream_id)
            stream_name = catalog_entry.tap_stream_id
            stream_schema = catalog_entry.schema.to_dict()
            stream_metadata = metadata.to_map(catalog_entry.metadata)
            stream_key_properties = catalog_entry.key_properties

            singer.write_schema(stream_name, stream_schema, stream_key_properties)

            replication_key = _get_replication_key(catalog_entry)
            path = _get_oracle_path(catalog_entry) or stream_to_path.get(stream_name)
            if not path:
                raise RuntimeError(
                    f"Could not resolve Oracle path for stream {stream_name}. "
                    "Run discovery with matching config or provide stream/resource overrides in config."
                )
            params: Dict[str, Any] = {}

            bookmark = None
            max_bookmark = None
            if replication_key:
                bookmark = _bookmark_value(
                    state,
                    stream_name,
                    replication_key,
                    str(config.get("start_date")),
                )
                params.update(_build_incremental_query(replication_key, bookmark))
                max_bookmark = bookmark

            LOGGER.info("START Syncing stream=%s path=%s", stream_name, path)
            update_currently_syncing(state, stream_name)

            record_count = 0
            for record in client.get_records(path, params=params):
                transformed_record = transformer.transform(
                    record,
                    stream_schema,
                    stream_metadata,
                )
                singer.write_record(stream_name, transformed_record)
                record_count += 1

                if replication_key:
                    record_replication_value = transformed_record.get(replication_key)
                    if isinstance(record_replication_value, str):
                        record_ts = _parse_timestamp(record_replication_value)
                        max_ts = _parse_timestamp(max_bookmark)
                        if record_ts and max_ts:
                            if record_ts > max_ts:
                                max_bookmark = record_replication_value
                        elif not max_bookmark or record_replication_value > max_bookmark:
                            max_bookmark = record_replication_value

            if replication_key and max_bookmark:
                state = _write_bookmark(state, stream_name, replication_key, max_bookmark)
                singer.write_state(state)

            update_currently_syncing(state, None)
            LOGGER.info("FINISHED Syncing stream=%s total_records=%s", stream_name, record_count)
