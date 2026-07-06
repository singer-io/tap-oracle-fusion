from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import singer
from singer import metadata

LOGGER = singer.get_logger()

REPLICATION_KEY_CANDIDATES = [
    "LastUpdateDate",
    "LastUpdatedDate",
    "LastUpdateDateTime",
    "UpdatedDate",
    "UpdatedOn",
    "CreationDate",
    "CreatedDate",
    "CreationDateTime",
]

_DATETIME_TYPE_NAMES = {
    "date",
    "datetime",
    "timestamp",
    "time",
    "offsetdatetime",
}


def _normalize_type_name(type_name: Optional[str]) -> str:
    return (type_name or "").strip().lower()


def _is_datetime_field(attribute_name: str, oracle_type: str) -> bool:
    field_name = attribute_name.lower()
    if oracle_type in _DATETIME_TYPE_NAMES:
        return True
    return (
        field_name.endswith("date")
        or field_name.endswith("time")
        or field_name.endswith("datetime")
        or field_name.endswith("_date")
        or field_name.endswith("_time")
    )


def oracle_attribute_to_property_schema(attribute: Mapping[str, Any]) -> Dict[str, Any]:
    """Map an Oracle describe attribute to a JSON schema property."""
    attr_type = _normalize_type_name(str(attribute.get("type", "string")))
    attr_name = str(attribute.get("name", "field"))

    if attr_type in {"string", "varchar", "char", "uuid"}:
        schema: Dict[str, Any] = {"type": ["null", "string"]}
    elif attr_type in {"integer", "int", "long", "short"}:
        schema = {"type": ["null", "integer"]}
    elif attr_type in {"number", "double", "decimal", "float"}:
        schema = {"type": ["null", "number"]}
    elif attr_type in {"boolean", "bool"}:
        schema = {"type": ["null", "boolean"]}
    elif attr_type in {"array", "list"}:
        schema = {
            "type": ["null", "array"],
            "items": {"type": ["null", "object"], "additionalProperties": True},
        }
    elif attr_type in {"object", "record", "map"}:
        schema = {"type": ["null", "object"], "additionalProperties": True}
    else:
        schema = {"type": ["null", "string"]}

    if _is_datetime_field(attr_name, attr_type) and "string" in schema.get("type", []):
        schema["format"] = "date-time"

    return schema


def _coerce_attribute_payload(entry: Any) -> List[Mapping[str, Any]]:
    if not isinstance(entry, Mapping):
        return []

    for key in ("attributes", "columns", "fields", "datastoreColumns"):
        values = entry.get(key)
        if isinstance(values, list):
            return [value for value in values if isinstance(value, Mapping)]

    return []


def _attribute_name(attribute: Mapping[str, Any]) -> Optional[str]:
    for key in ("name", "columnName", "attributeName", "fieldName"):
        value = attribute.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _attribute_type(attribute: Mapping[str, Any]) -> str:
    for key in ("type", "dataType", "columnType"):
        value = attribute.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "string"


def infer_bicc_primary_keys(attributes: Iterable[Mapping[str, Any]]) -> List[str]:
    primary_keys: List[str] = []
    seen = set()

    for attribute in attributes:
        name = _attribute_name(attribute)
        if not name:
            continue
        if bool(attribute.get("isPrimaryKey")) and name not in seen:
            primary_keys.append(name)
            seen.add(name)

    return primary_keys


def infer_bicc_replication_key(attributes: Iterable[Mapping[str, Any]]) -> Optional[str]:
    for attribute in attributes:
        name = _attribute_name(attribute)
        if name and bool(attribute.get("isLastUpdateDate")):
            return name

    for attribute in attributes:
        name = _attribute_name(attribute)
        if name and bool(attribute.get("isCreationDate")):
            return name

    return None


def build_bicc_schema(detail_payload: Any) -> Dict[str, Any]:
    """Build JSON schema from BICC datastore detail payload."""
    properties: Dict[str, Any] = {}
    for attribute in _coerce_attribute_payload(detail_payload):
        attr_name = _attribute_name(attribute)
        if not attr_name:
            continue

        properties[attr_name] = oracle_attribute_to_property_schema(
            {"name": attr_name, "type": _attribute_type(attribute)}
        )

    schema: Dict[str, Any] = {"type": "object", "properties": properties}
    if not properties:
        schema["additionalProperties"] = True
    return schema


def build_bicc_schema_and_metadata(
    detail_payload: Any,
    oracle_path: str,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[str]]:
    """Build Singer schema and metadata for a BICC datastore detail payload."""
    attributes = _coerce_attribute_payload(detail_payload)
    schema_dict = build_bicc_schema(detail_payload)
    primary_keys = infer_bicc_primary_keys(attributes)
    replication_key = infer_bicc_replication_key(attributes)

    primary_key = primary_keys[0] if primary_keys else None
    replication_method = "INCREMENTAL" if replication_key else "FULL_TABLE"
    mdata = metadata.get_standard_metadata(
        schema=schema_dict,
        key_properties=[primary_key] if primary_key else [],
        valid_replication_keys=[replication_key] if replication_key else [],
        replication_method=replication_method,
    )

    mdata_map = metadata.to_map(mdata)
    if replication_key:
        mdata_map = metadata.write(
            mdata_map,
            ("properties", replication_key),
            "inclusion",
            "automatic",
        )
    mdata_map = metadata.write(mdata_map, (), "oracle-path", oracle_path)
    return schema_dict, metadata.to_list(mdata_map), primary_keys


def _extract_attributes(describe_payload: Mapping[str, Any], resource_name: str) -> List[Mapping[str, Any]]:
    resources_obj = describe_payload.get("Resources", {})
    if isinstance(resources_obj, Mapping):
        resource_obj = resources_obj.get(resource_name) or resources_obj.get(resource_name.lower())
        if isinstance(resource_obj, Mapping):
            attributes = resource_obj.get("attributes", [])
            if isinstance(attributes, list):
                return [item for item in attributes if isinstance(item, Mapping)]

    attributes = describe_payload.get("attributes", [])
    if isinstance(attributes, list):
        return [item for item in attributes if isinstance(item, Mapping)]

    return []


def infer_primary_key(resource_name: str, describe_payload: Mapping[str, Any], attributes: Iterable[Mapping[str, Any]]) -> Optional[str]:
    """Infer PK from finder metadata, then fallback to id-like attributes."""
    resources_obj = describe_payload.get("Resources", {})
    if isinstance(resources_obj, Mapping):
        resource_obj = resources_obj.get(resource_name) or resources_obj.get(resource_name.lower())
        if isinstance(resource_obj, Mapping):
            collection = resource_obj.get("collection", {})
            if isinstance(collection, Mapping):
                finders = collection.get("finders", [])
                if isinstance(finders, list):
                    for finder in finders:
                        if not isinstance(finder, Mapping):
                            continue
                        if str(finder.get("name", "")).lower() != "primarykey":
                            continue
                        finder_attributes = finder.get("attributes", [])
                        if isinstance(finder_attributes, list) and finder_attributes:
                            first_attr = finder_attributes[0]
                            if isinstance(first_attr, Mapping):
                                attr_name = first_attr.get("name")
                                if isinstance(attr_name, str) and attr_name:
                                    return attr_name

    attr_names = [str(item.get("name", "")) for item in attributes if item.get("name")]
    for candidate in attr_names:
        lowered = candidate.lower()
        if lowered == "id" or lowered.endswith("id"):
            return candidate

    return None


def infer_replication_key(attributes: Iterable[Mapping[str, Any]]) -> Optional[str]:
    name_to_attr = {
        str(attr.get("name")): attr
        for attr in attributes
        if isinstance(attr.get("name"), str)
    }

    for candidate in REPLICATION_KEY_CANDIDATES:
        if candidate in name_to_attr:
            return candidate

    for name, attr in name_to_attr.items():
        type_name = _normalize_type_name(str(attr.get("type", "")))
        if _is_datetime_field(name, type_name) and bool(attr.get("queryable", True)):
            return name

    return None


def build_schema(attributes: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    properties: Dict[str, Any] = {}
    for attribute in attributes:
        name = attribute.get("name")
        if not isinstance(name, str) or not name:
            continue
        properties[name] = oracle_attribute_to_property_schema(attribute)

    return {
        "type": "object",
        "properties": properties,
    }


def _observed_json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return "string"


def _merge_types(current_types: List[str], observed_type: str) -> List[str]:
    ordered = ["null", "boolean", "integer", "number", "string", "array", "object"]
    merged = set(current_types)
    merged.add(observed_type)

    if "integer" in merged and "number" in merged:
        merged.discard("integer")

    return [value for value in ordered if value in merged]


def enrich_schema_with_samples(schema: Dict[str, Any], sample_records: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    """Merge observed sample payload types into generated schema properties."""
    properties = schema.setdefault("properties", {})
    for record in sample_records:
        if not isinstance(record, Mapping):
            continue
        for key, value in record.items():
            observed_type = _observed_json_type(value)

            if key not in properties:
                properties[key] = {"type": ["null", observed_type]}
            else:
                raw_types = properties[key].get("type", ["null", "string"])
                current_types = [raw_types] if isinstance(raw_types, str) else list(raw_types)
                properties[key]["type"] = _merge_types(current_types, observed_type)

            if _is_datetime_field(key, "") and "string" in properties[key].get("type", []):
                properties[key]["format"] = "date-time"

    return schema


def build_metadata(schema: Mapping[str, Any], primary_key: Optional[str], replication_key: Optional[str]) -> List[Dict[str, Any]]:
    replication_method = "INCREMENTAL" if replication_key else "FULL_TABLE"
    mdata = metadata.new()
    mdata = metadata.get_standard_metadata(
        schema=schema,
        key_properties=[primary_key] if primary_key else [],
        valid_replication_keys=[replication_key] if replication_key else [],
        replication_method=replication_method,
    )
    mdata = metadata.to_map(mdata)

    if replication_key:
        mdata = metadata.write(
            mdata,
            ("properties", replication_key),
            "inclusion",
            "automatic",
        )

    return metadata.to_list(mdata)


def build_schema_and_metadata(
    resource_name: str,
    describe_payload: Mapping[str, Any],
    sample_records: Optional[Iterable[Mapping[str, Any]]] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Optional[str], Optional[str]]:
    """Build Singer schema + metadata from a resource describe payload."""
    attributes = _extract_attributes(describe_payload, resource_name)
    schema = build_schema(attributes)

    if sample_records:
        schema = enrich_schema_with_samples(schema, sample_records)

    primary_key = infer_primary_key(resource_name, describe_payload, attributes)
    if primary_key and primary_key not in schema.get("properties", {}):
        schema["properties"][primary_key] = {"type": ["null", "string"]}

    replication_key = infer_replication_key(attributes)
    metadata_list = build_metadata(schema, primary_key, replication_key)

    return schema, metadata_list, primary_key, replication_key
