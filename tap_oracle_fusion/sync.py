"""Sync logic for Oracle Fusion REST and BICC datastore streams."""
from datetime import datetime, timezone
import hashlib
import math
from typing import Any, Dict, List, Mapping, Optional, Union
from urllib.parse import unquote

import singer
from singer import metadata

from tap_oracle_fusion.client import OracleClient
from tap_oracle_fusion.bicc_extract import (
    BICCExtractClient,
    DEFAULT_INITIAL_EXTRACT_DATE,
    ExtractError,
)
from tap_oracle_fusion.discover import get_stream_resource_map
from tap_oracle_fusion.schema import DATASTORE_KEY_METADATA_KEY, ENTITY_SET_METADATA_KEY

LOGGER = singer.get_logger()


def _sanitize_float_values(obj: Any) -> Any:
    """Replace non-finite floats (nan/inf) with None for JSON compliance."""
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {k: _sanitize_float_values(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_float_values(v) for v in obj]
    return obj


def _parse_timestamp(timestamp_value: Optional[str]) -> Optional[datetime]:
    if not timestamp_value or not isinstance(timestamp_value, str):
        return None

    normalized = timestamp_value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
        # ensure timezone-aware so comparisons never mix naive and aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _state_is_valid(state: Dict[str, Any]) -> bool:
    return isinstance(state, dict) and (
        "bookmarks" not in state or isinstance(state.get("bookmarks"), dict)
    )


def update_currently_syncing(state: Dict[str, Any], stream_name: Optional[str]) -> None:
    """Update and write the currently_syncing key in state."""
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
    return unquote(raw).strip()


def _get_datastore_name(catalog_entry: singer.CatalogEntry, path: str) -> Optional[str]:
    stream_meta = _get_stream_meta(catalog_entry)
    datastore = stream_meta.get(DATASTORE_KEY_METADATA_KEY)
    if isinstance(datastore, str) and datastore:
        return datastore.strip()
    return _datastore_from_path(path)


def _schema_property_lookup(stream_schema: Mapping[str, Any]) -> Dict[str, str]:
    properties = stream_schema.get("properties")
    if not isinstance(properties, Mapping):
        return {}
    return {
        key.lower(): key
        for key in properties.keys()
        if isinstance(key, str)
    }


def _normalize_record_keys_for_schema(
    record: Mapping[str, Any], property_lookup: Mapping[str, str]
) -> Dict[str, Any]:
    if not property_lookup:
        return dict(record)

    normalized: Dict[str, Any] = {}
    for key, value in record.items():
        if not isinstance(key, str):
            normalized[key] = value
            continue
        canonical_key = property_lookup.get(key.lower(), key)
        normalized[canonical_key] = value
    return normalized


def _is_datetime_property(prop_schema: Any) -> bool:
    return isinstance(prop_schema, Mapping) and prop_schema.get("format") == "date-time"


def _datetime_schema_fields(stream_schema: Mapping[str, Any]) -> set[str]:
    properties = stream_schema.get("properties")
    if not isinstance(properties, Mapping):
        return set()

    return {
        field_name
        for field_name, field_schema in properties.items()
        if isinstance(field_name, str) and _is_datetime_property(field_schema)
    }


def _is_valid_datetime_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return True
        normalized = text.replace("Z", "+00:00")
        try:
            datetime.fromisoformat(normalized)
            return True
        except ValueError:
            return False
    return False


def _sanitize_record_datetimes_for_schema(
    record: Mapping[str, Any],
    datetime_fields: set[str],
    stream_name: str,
    warned_values: set[tuple[str, str, str]],
) -> Dict[str, Any]:
    if not datetime_fields:
        return dict(record)

    sanitized = dict(record)
    for field in datetime_fields:
        if field not in sanitized:
            continue
        value = sanitized[field]
        if _is_valid_datetime_value(value):
            continue
        warning_key = (stream_name, field, repr(value))
        if warning_key not in warned_values:
            warned_values.add(warning_key)
            LOGGER.warning(
                "stream=%s field=%s has invalid date-time value %r; writing null",
                stream_name,
                field,
                value,
            )
        sanitized[field] = None
    return sanitized


def _is_unsupported_datastore_create_job_error(error: Exception) -> bool:
    message = str(error)
    return (
        "JBO-26048" in message
        and "C_JOB_DATA_STORE_REL_C_DA_FK1" in message
    )


def _metadata_path_is_bicc(path: str) -> bool:
    return path.startswith("biacm/rest/meta/datastores/")


def _bookmark_value(
    state: Dict[str, Any], stream: str, replication_key: str, start_date: str
) -> str:
    return singer.get_bookmark(state, stream, replication_key, start_date)


def _write_bookmark(
    state: Dict[str, Any], stream: str, replication_key: str, value: str
) -> Dict[str, Any]:
    return singer.write_bookmark(state, stream, replication_key, value)


def _build_incremental_query(
    replication_key: str,
    bookmark_value: str,
) -> Dict[str, Any]:
    """Build Oracle query parameter for incremental filtering."""
    query_expression = f"{replication_key}>='{bookmark_value}'"
    return {"q": query_expression}


def sync(config: Mapping[str, Any], catalog: singer.Catalog, state: Dict[str, Any]) -> None:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    """Run the sync loop for all selected streams."""
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
            schema_property_lookup = _schema_property_lookup(stream_schema)
            datetime_fields = _datetime_schema_fields(stream_schema)
            warned_invalid_datetime_values: set[tuple[str, str, str]] = set()

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
                    "Run discovery with matching config or provide "
                    "stream/resource overrides in config."
                )
            params: Dict[str, Any] = {}

            bookmark = None
            max_bookmark = None
            if replication_key:
                bookmark = _bookmark_value(
                    state,
                    stream_name,
                    replication_key,
                    config.get("start_date", ""),
                )
                params.update(_build_incremental_query(replication_key, bookmark))
                max_bookmark = bookmark

            LOGGER.info("START Syncing stream=%s path=%s", stream_name, path)
            update_currently_syncing(state, stream_name)

            record_count = 0
            records_iter = None
            is_bicc_stream = _metadata_path_is_bicc(path)
            if is_bicc_stream:
                datastore = _get_datastore_name(catalog_entry, path)
                if not datastore:
                    raise RuntimeError(
                        f"Could not resolve BICC datastore name for stream {stream_name}."
                    )
                try:
                    job_name = f"file_{bicc_client.datastore_slug(datastore)}"
                    if force_full:
                        suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
                        job_name = f"{job_name}__full_{suffix}"
                    job_id = bicc_client.create_bicc_job(
                        datastore=datastore,
                        initial_extract_date=initial_extract_date,
                        job_name=job_name,
                    )

                    records_iter, _ = bicc_client.run_extract_to_rows(
                        datastore=datastore,
                        job_id=job_id,
                        ess_poll_interval=ess_poll_interval,
                        ess_max_polls=ess_max_polls,
                        ucm_poll_interval=ucm_poll_interval,
                        ucm_max_attempts=ucm_max_attempts,
                    )
                except ExtractError as err:
                    if _is_unsupported_datastore_create_job_error(err):
                        LOGGER.warning(
                            "Skipping stream=%s datastore=%s due to unsupported "
                            "Oracle BICC create-job constraint: %s",
                            stream_name,
                            datastore,
                            err,
                        )
                        update_currently_syncing(state, None)
                        continue
                    LOGGER.error(
                        "Skipping stream=%s datastore=%s due to ESS extract error: %s",
                        stream_name,
                        datastore,
                        err,
                    )
                    update_currently_syncing(state, None)
                    continue
            else:
                records_iter = client.get_records(path, params=params)

            seen_bicc_pks: set = set()
            for record in records_iter:
                if is_bicc_stream:
                    record = _normalize_record_keys_for_schema(record, schema_property_lookup)
                    record = _sanitize_record_datetimes_for_schema(
                        record,
                        datetime_fields,
                        stream_name,
                        warned_invalid_datetime_values,
                    )
                    if stream_key_properties:
                        pk_tuple = tuple(record.get(pk) for pk in sorted(stream_key_properties))
                        pk_hash = hashlib.sha256(repr(pk_tuple).encode()).digest()
                        if pk_hash in seen_bicc_pks:
                            continue
                        seen_bicc_pks.add(pk_hash)
                    if replication_key and bookmark:
                        record_replication_value = record.get(replication_key)
                        if record_replication_value:
                            record_ts = _parse_timestamp(record_replication_value)
                            bookmark_ts = _parse_timestamp(bookmark)
                            if record_ts and bookmark_ts and record_ts < bookmark_ts:
                                continue
                transformed_record = transformer.transform(
                    record,
                    stream_schema,
                    stream_metadata,
                )
                transformed_record = _sanitize_float_values(transformed_record)
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
