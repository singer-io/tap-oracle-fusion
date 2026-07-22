from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional
from urllib.parse import unquote

import singer
from singer import metadata

from tap_oracle_fusion.client import OracleClient
from tap_oracle_fusion.bicc_extract import (
    BICCExtractClient,
    DEFAULT_INITIAL_EXTRACT_DATE,
)
from tap_oracle_fusion.discover import get_stream_resource_map
from tap_oracle_fusion.schema import DATASTORE_KEY_METADATA_KEY, ENTITY_SET_METADATA_KEY

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
    oracle_path = stream_meta.get(ENTITY_SET_METADATA_KEY)
    if isinstance(oracle_path, str) and oracle_path:
        return oracle_path
    return ""


def _datastore_from_path(path: str) -> Optional[str]:
    if not path:
        return None
    prefix = "biacm/rest/meta/datastores/"
    idx = path.find(prefix)
    if idx < 0:
        return None
    raw = path[idx + len(prefix):]
    if not raw:
        return None
    return unquote(raw)


def _get_datastore_name(catalog_entry: singer.CatalogEntry, path: str) -> Optional[str]:
    stream_meta = _get_stream_meta(catalog_entry)
    datastore = stream_meta.get(DATASTORE_KEY_METADATA_KEY)
    if isinstance(datastore, str) and datastore:
        return datastore
    return _datastore_from_path(path)


def _stream_bookmark_value(state: Dict[str, Any], stream: str, key: str, default: Optional[str] = None) -> Optional[str]:
    return singer.get_bookmark(state, stream, key, default)


def _write_stream_bookmark(state: Dict[str, Any], stream: str, key: str, value: str) -> Dict[str, Any]:
    return singer.write_bookmark(state, stream, key, value)


def _metadata_path_is_bicc(path: str) -> bool:
    return path.startswith("biacm/rest/meta/datastores/")


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
    bicc_client = BICCExtractClient(config)
    stream_to_path: Optional[Dict[str, str]] = None
    selected_streams = catalog.get_selected_streams(state)
    ess_poll_interval = int(config.get("ess_poll_interval_seconds", 20))
    ess_max_polls = int(config.get("ess_max_polls", 30))
    ucm_poll_interval = int(config.get("ucm_poll_interval_seconds", 12))
    ucm_max_attempts = int(config.get("ucm_max_attempts", 30))
    initial_extract_date = str(config.get("initial_extract_date", DEFAULT_INITIAL_EXTRACT_DATE))
    force_full = bool(config.get("bicc_force_full_sync", False))
    with singer.Transformer() as transformer:
        for selected_stream in selected_streams:
            catalog_entry = catalog.get_stream(selected_stream.tap_stream_id)
            stream_name = catalog_entry.tap_stream_id
            stream_schema = catalog_entry.schema.to_dict()
            stream_metadata = metadata.to_map(catalog_entry.metadata)
            stream_key_properties = catalog_entry.key_properties

            singer.write_schema(stream_name, stream_schema, stream_key_properties)

            replication_key = _get_replication_key(catalog_entry)
            path = _get_oracle_path(catalog_entry)
            if not path:
                if stream_to_path is None:
                    LOGGER.info(
                        "Catalog missing entity-set metadata for one or more streams; "
                        "resolving stream paths from discovery candidates."
                    )
                    stream_to_path = get_stream_resource_map(config)
                path = stream_to_path.get(stream_name)
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
            records_iter = None
            if _metadata_path_is_bicc(path):
                datastore = _get_datastore_name(catalog_entry, path)
                if not datastore:
                    raise RuntimeError(
                        f"Could not resolve BICC datastore name for stream {stream_name}."
                    )

                existing_job_id = _stream_bookmark_value(state, stream_name, "bicc_job_id")
                create_new_job = force_full or not existing_job_id
                if create_new_job:
                    job_name = f"file_{bicc_client.datastore_slug(datastore)}"
                    if force_full:
                        suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
                        job_name = f"{job_name}__full_{suffix}"
                    job_id = bicc_client.create_bicc_job(
                        datastore=datastore,
                        initial_extract_date=initial_extract_date,
                        job_name=job_name,
                    )
                    state = _write_stream_bookmark(state, stream_name, "bicc_job_id", job_id)
                    singer.write_state(state)
                else:
                    job_id = str(existing_job_id)

                records_iter, _ = bicc_client.run_extract_to_rows(
                    datastore=datastore,
                    job_id=job_id,
                    ess_poll_interval=ess_poll_interval,
                    ess_max_polls=ess_max_polls,
                    ucm_poll_interval=ucm_poll_interval,
                    ucm_max_attempts=ucm_max_attempts,
                )
            else:
                records_iter = client.get_records(path, params=params)

            for record in records_iter:
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

            if replication_key and max_bookmark and not _metadata_path_is_bicc(path):
                state = _write_bookmark(state, stream_name, replication_key, max_bookmark)
                singer.write_state(state)

            update_currently_syncing(state, None)
            LOGGER.info("FINISHED Syncing stream=%s total_records=%s", stream_name, record_count)
