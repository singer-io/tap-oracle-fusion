"""Discovery logic for Oracle Fusion BICC datastore catalog generation."""
import re
import threading
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

import singer
from singer.catalog import Catalog, CatalogEntry, Schema

from tap_oracle_fusion.client import OracleClient, OracleClientError
from tap_oracle_fusion.schema import build_bicc_schema_and_metadata

LOGGER = singer.get_logger()
BICC_DATASTORES_PATH = "biacm/rest/meta/datastores"
DISCOVERY_LIMIT_KEYS = ("discovery_limit",)
DISCOVERY_WORKER_KEYS = ("discovery_workers", 8)
DISCOVERY_PARENTS_KEY = "discovery_parents"
DISCOVERY_PROGRESS_LOG_EVERY = 250


def _normalize_stream_name(resource_name: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", resource_name.strip().lower())
    return normalized.strip("_")


def _to_lowercase_set(values: Iterable[str]) -> Set[str]:
    return {
        value.lower()
        for value in values
        if isinstance(value, str) and value.strip()
    }


def _iter_configured_datastores(config: Mapping[str, Any]) -> Iterable[str]:
    configured = config.get("streams") or config.get("datastores") or config.get("resources")
    if not configured:
        return []

    output: List[str] = []
    if isinstance(configured, list):
        for item in configured:
            if isinstance(item, str):
                output.append(item)
            elif isinstance(item, Mapping):
                name = item.get("name") or item.get("datastore") or item.get("resource")
                if isinstance(name, str):
                    output.append(name)
    return output


def _iter_configured_parents(config: Mapping[str, Any]) -> Iterable[str]:
    configured = config.get(DISCOVERY_PARENTS_KEY)

    if configured is None:
        return []

    if isinstance(configured, str):
        return [part.strip() for part in configured.split(",") if part.strip()]

    if isinstance(configured, (list, tuple, set)):
        return [item.strip() for item in configured if isinstance(item, str) and item.strip()]

    return []


def _extract_datastore_entries(payload: Mapping[str, Any]) -> List[Any]:
    for key in ("dataStores", "datastores", "items", "data", "results"):
        values = payload.get(key)
        if isinstance(values, list):
            return values
    return []


def _extract_datastore_name(entry: Any) -> Optional[str]:
    if isinstance(entry, str) and entry.strip():
        return entry.strip()

    if isinstance(entry, Mapping):
        for key in ("name", "datastore", "datastoreName", "pvoName", "id"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return None


def _build_datastore_detail_path(datastore_name: str) -> str:
    # Names can include spaces/special characters; URL-encode path segment safely.
    return f"{BICC_DATASTORES_PATH}/{quote(datastore_name, safe='')}"


def _datastore_matches_any_parent(datastore_name: str, configured_parents: Set[str]) -> bool:
    lowered = datastore_name.lower()
    return any(
        lowered == parent or lowered.startswith(parent + ".")
        for parent in configured_parents
    )


def _get_discovery_limit(config: Mapping[str, Any]) -> Optional[int]:
    for key in DISCOVERY_LIMIT_KEYS:
        value = config.get(key)
        if value is None:
            continue
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            return parsed
    return None


def _get_discovery_workers(config: Mapping[str, Any]) -> int:
    key, default = DISCOVERY_WORKER_KEYS
    value = config.get(key)
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _list_datastores(client: OracleClient) -> List[Any]:
    """Fetch all datastore entries in a single request (the API does not support pagination)."""
    payload = client.get(BICC_DATASTORES_PATH)
    entries = _extract_datastore_entries(payload)
    LOGGER.info("Datastores received: %s", len(entries))
    return entries


def _list_discovery_candidates(client: OracleClient, config: Mapping[str, Any]) -> List[str]:
    configured_datastores = _to_lowercase_set(_iter_configured_datastores(config))
    configured_parents = _to_lowercase_set(_iter_configured_parents(config))
    discovery_limit = _get_discovery_limit(config)

    candidates: List[str] = []
    seen_names: Set[str] = set()
    for entry in _list_datastores(client):
        datastore_name = _extract_datastore_name(entry)
        if not datastore_name:
            continue

        lowered = datastore_name.lower()
        if configured_parents and not _datastore_matches_any_parent(datastore_name, configured_parents):
            continue
        if configured_datastores and lowered not in configured_datastores:
            continue
        if lowered in seen_names:
            continue

        seen_names.add(lowered)
        candidates.append(datastore_name)

        if discovery_limit and len(candidates) >= discovery_limit:
            break

    if configured_parents:
        LOGGER.info(
            "Applying discovery parent filter: %s (matched %s datastore(s))",
            sorted(configured_parents),
            len(candidates),
        )

    return candidates


def _load_datastore_detail(
    client: OracleClient,
    datastore_name: str,
    detail_path: str,
) -> Tuple[Any, Optional[str], bool]:
    """Load datastore detail payload and return a skip reason when detail fetch fails."""
    try:
        return client.get(detail_path), None, False
    except Exception as err:  # pragma: no cover - defensive logging branch  # pylint: disable=broad-exception-caught
        if isinstance(err, OracleClientError):
            should_retry = err.retryable
        else:
            should_retry = True
        LOGGER.warning(
            "Unable to fetch datastore detail for %s (%s).",
            datastore_name,
            err,
        )
        return {}, str(err), should_retry


def _build_catalog_entry(
    datastore_name: str,
    stream_name: str,
    detail_path: str,
    detail_payload: Any,
    skip_reason: Optional[str] = None,
) -> Tuple[Optional[CatalogEntry], Optional[str]]:
    schema_dict, mdata, primary_keys = build_bicc_schema_and_metadata(
        detail_payload=detail_payload,
        oracle_path=detail_path,
        datastore_name=datastore_name,
    )

    if not schema_dict.get("properties"):
        exclusion_reason = skip_reason or "schema metadata was empty"
        return None, exclusion_reason

    return (
        CatalogEntry(
            stream=stream_name,
            tap_stream_id=stream_name,
            key_properties=primary_keys,
            schema=Schema.from_dict(schema_dict),
            metadata=mdata,
        ),
        None,
    )


class BICCDiscoveryRunner:  # pylint: disable=too-many-instance-attributes
    """Class-based discovery runner for BICC datastore discovery."""

    def __init__(self, config: Mapping[str, Any]) -> None:
        self.config = config
        self.client = OracleClient(config)
        self.worker_count = _get_discovery_workers(config)
        self._thread_local = threading.local()
        self._progress_lock = threading.Lock()
        self._skip_lock = threading.Lock()
        self._processed_count = 0
        self._total_count = 0
        self._skipped_datastores: List[Tuple[str, str]] = []

    def _get_thread_client(self) -> OracleClient:
        """Return a per-thread OracleClient, creating one on first access."""
        client = getattr(self._thread_local, "client", None)
        if client is None:
            client = OracleClient(self.config)
            self._thread_local.client = client
        return client

    def list_candidates(self) -> List[str]:
        """Return the list of datastore names to discover."""
        return _list_discovery_candidates(self.client, self.config)

    @staticmethod
    def _detail_path(datastore_name: str) -> str:
        return _build_datastore_detail_path(datastore_name)

    def _build_entry(
        self,
        datastore_name: str,
        use_thread_client: bool,
    ) -> Tuple[Optional[CatalogEntry], bool]:
        stream_name = _normalize_stream_name(datastore_name)
        detail_path = self._detail_path(datastore_name)
        detail_client = self._get_thread_client() if use_thread_client else self.client
        detail_payload, skip_reason, retryable_failure = _load_datastore_detail(
            detail_client,
            datastore_name,
            detail_path,
        )
        entry, exclusion_reason = _build_catalog_entry(
            datastore_name=datastore_name,
            stream_name=stream_name,
            detail_path=detail_path,
            detail_payload=detail_payload,
            skip_reason=skip_reason,
        )
        if exclusion_reason:
            return None, retryable_failure

        return entry, False

    def _build_entries_sequential(
        self, datastore_names: List[str]
    ) -> List[CatalogEntry]:
        entries: List[CatalogEntry] = []
        for name in datastore_names:
            entry, _ = self._build_entry(name, use_thread_client=False)
            self._log_progress(name)
            if entry is not None:
                entries.append(entry)
            else:
                with self._skip_lock:
                    self._skipped_datastores.append((name, "discovery failure"))
        return entries

    def _build_entries_threaded(
        self, datastore_names: List[str]
    ) -> List[CatalogEntry]:
        results: List[Optional[CatalogEntry]] = [None] * len(datastore_names)

        with ThreadPoolExecutor(max_workers=self.worker_count) as executor:
            future_to_index = {
                executor.submit(self._build_entry, datastore_name, True): index
                for index, datastore_name in enumerate(datastore_names)
            }
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                entry, _ = future.result()
                results[index] = entry
                if entry is None:
                    with self._skip_lock:
                        self._skipped_datastores.append(
                            (datastore_names[index], "discovery failure")
                        )
                self._log_progress(datastore_names[index])

        return [entry for entry in results if entry is not None]

    def _log_progress(self, datastore_name: str) -> None:
        with self._progress_lock:
            self._processed_count += 1
            processed = self._processed_count
            total = self._total_count

        if processed == 1 or processed % DISCOVERY_PROGRESS_LOG_EVERY == 0 or processed == total:
            remaining = max(total - processed, 0)
            LOGGER.info(
                "Discovery progress: %s/%s processed, %s left (latest datastore: %s)",
                processed,
                total,
                remaining,
                datastore_name,
            )

    def _log_skipped_datastores(self) -> None:
        if not self._skipped_datastores:
            return

        datastore_names = sorted({datastore_name for datastore_name, _ in self._skipped_datastores})
        names_suffix = ", ".join(datastore_names)

        LOGGER.warning(
            "Excluding %s datastore(s) from catalog: %s",
            len(datastore_names),
            names_suffix,
        )

    def discover(self) -> Catalog:
        """Run discovery and return a Singer Catalog with all found BICC streams."""
        datastore_names = self.list_candidates()
        self._total_count = len(datastore_names)
        self._processed_count = 0
        LOGGER.info(
            "Discovering %s BICC datastores with %s worker(s)",
            len(datastore_names),
            self.worker_count,
        )

        if self.worker_count <= 1 or len(datastore_names) <= 1:
            entries = self._build_entries_sequential(datastore_names)
        else:
            entries = self._build_entries_threaded(datastore_names)

        self._log_skipped_datastores()
        return Catalog(streams=entries)


def get_stream_resource_map(config: Mapping[str, Any]) -> Dict[str, str]:
    """Map normalized stream names to BICC datastore metadata paths."""
    client = OracleClient(config)

    stream_to_path: Dict[str, str] = {}
    for datastore_name in _list_discovery_candidates(client, config):
        stream_name = _normalize_stream_name(datastore_name)
        if stream_name in stream_to_path:
            continue
        stream_to_path[stream_name] = _build_datastore_detail_path(datastore_name)

    return stream_to_path


def discover(config: Mapping[str, Any]) -> Catalog:
    """Discover Oracle Fusion BICC datastores and emit dynamic Singer catalog entries."""
    return BICCDiscoveryRunner(config).discover()
