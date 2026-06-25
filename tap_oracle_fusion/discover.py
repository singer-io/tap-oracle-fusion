from typing import Any, Dict, Iterable, List, Mapping, Set

import singer
from singer.catalog import Catalog, CatalogEntry, Schema

from tap_oracle_fusion.client import OracleClient
from tap_oracle_fusion.schema import build_schema_and_metadata

LOGGER = singer.get_logger()


def _normalize_stream_name(resource_name: str) -> str:
    return resource_name.strip().replace(" ", "_").replace("-", "_").lower()


def _get_versions_for_family(config: Mapping[str, Any], family: str) -> List[str]:
    api_versions = config.get("api_versions")
    if isinstance(api_versions, Mapping) and api_versions.get(family):
        return [str(api_versions[family])]

    if config.get("api_version"):
        return [str(config["api_version"])]

    return ["11.13.18.05"]


def _extract_resource_names(payload: Mapping[str, Any]) -> List[str]:
    names: Set[str] = set()
    # Exclude known non-resource entries (HATEOAS links, metadata)
    excluded = {"canonical", "describe", "predecessor-version", "self", "child", "parent"}

    resources_obj = payload.get("Resources")
    if isinstance(resources_obj, Mapping):
        names.update(str(key) for key in resources_obj.keys() if key and str(key).lower() not in excluded)

    items = payload.get("items")
    if isinstance(items, list):
        for item in items:
            if isinstance(item, Mapping):
                for key in ("name", "resourceName", "id"):
                    value = item.get(key)
                    if isinstance(value, str) and value and str(value).lower() not in excluded:
                        names.add(value)
                        break

    links = payload.get("links")
    if isinstance(links, list):
        for link in links:
            if not isinstance(link, Mapping):
                continue
            name = link.get("name")
            href = link.get("href")
            if isinstance(name, str) and name and str(name).lower() not in excluded:
                names.add(name)
            elif isinstance(href, str) and "/resources/" in href:
                candidate = href.rstrip("/").split("/")[-1]
                if candidate and candidate.lower() not in excluded:
                    names.add(candidate)

    return sorted(names)


def _list_resources(client: OracleClient, family: str, version: str) -> List[str]:
    path = f"{family}RestApi/resources/{version}/describe"
    payload = client.get(path)
    resources = _extract_resource_names(payload)
    if not resources:
        raise RuntimeError(f"No resources returned for family={family} version={version}")
    return resources


def _iter_configured_resources(config: Mapping[str, Any]) -> Iterable[str]:
    configured = config.get("streams") or config.get("resources")
    if not configured:
        return []

    output: List[str] = []
    if isinstance(configured, list):
        for item in configured:
            if isinstance(item, str):
                output.append(item)
            elif isinstance(item, Mapping):
                name = item.get("name") or item.get("resource")
                if isinstance(name, str):
                    output.append(name)
    return output


def get_stream_resource_map(config: Mapping[str, Any]) -> Dict[str, str]:
    """Map normalized stream names to Oracle collection paths without mutating catalog metadata."""
    client = OracleClient(config)
    configured_resources = list(_iter_configured_resources(config))
    families = config.get("api_families") or ["hcm", "fscm"]

    work_items = []
    if configured_resources:
        default_family = str(config.get("default_family", "hcm"))
        default_version = _get_versions_for_family(config, default_family)[0]
        for resource in configured_resources:
            work_items.append((default_family, default_version, str(resource)))
    else:
        for family in families:
            family_name = str(family)
            versions = _get_versions_for_family(config, family_name)
            for version in versions:
                try:
                    for resource in _list_resources(client, family_name, version):
                        work_items.append((family_name, version, resource))
                except Exception as err:  # pragma: no cover - defensive logging branch
                    LOGGER.warning(
                        "Skipping family=%s version=%s while building stream map: %s",
                        family_name,
                        version,
                        err,
                    )

    stream_to_path: Dict[str, str] = {}
    for family, version, resource in work_items:
        stream_name = _normalize_stream_name(resource)
        if stream_name in stream_to_path:
            continue
        stream_to_path[stream_name] = f"{family}RestApi/resources/{version}/{resource}"

    return stream_to_path


def discover(config: Mapping[str, Any]) -> Catalog:
    """Discover Oracle Fusion resources and emit dynamic Singer catalog entries."""
    client = OracleClient(config)
    catalog = Catalog(streams=[])

    configured_resources = list(_iter_configured_resources(config))
    families = config.get("api_families") or ["hcm", "fscm"]

    if configured_resources:
        work_items = [(str(config.get("default_family", "hcm")), str(resource)) for resource in configured_resources]
    else:
        work_items = []
        for family in families:
            family_name = str(family)
            versions = _get_versions_for_family(config, family_name)
            for version in versions:
                try:
                    for resource in _list_resources(client, family_name, version):
                        work_items.append((family_name, resource))
                except Exception as err:  # pragma: no cover - defensive logging branch
                    LOGGER.warning(
                        "Skipping family=%s version=%s during resource enumeration: %s",
                        family_name,
                        version,
                        err,
                    )

    seen_streams: Set[str] = set()
    for family, resource in work_items:
        stream_name = _normalize_stream_name(resource)
        if stream_name in seen_streams:
            continue

        versions = _get_versions_for_family(config, family)
        describe_payload = None
        selected_version = None
        for version in versions:
            describe_path = f"{family}RestApi/resources/{version}/{resource}/describe"
            try:
                describe_payload = client.get(describe_path)
                selected_version = version
                break
            except Exception as err:
                LOGGER.warning(
                    "Unable to describe resource=%s family=%s version=%s: %s",
                    resource,
                    family,
                    version,
                    err,
                )

        if not describe_payload:
            continue

        schema_dict, mdata, primary_key, _replication_key = build_schema_and_metadata(
            resource_name=resource,
            describe_payload=describe_payload,
        )
        schema = Schema.from_dict(schema_dict)

        catalog.streams.append(
            CatalogEntry(
                stream=stream_name,
                tap_stream_id=stream_name,
                key_properties=[primary_key] if primary_key else [],
                schema=schema,
                metadata=mdata,
            )
        )
        seen_streams.add(stream_name)

    return catalog
