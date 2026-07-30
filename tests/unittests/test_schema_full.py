"""Additional tests for tap_oracle_fusion.schema module."""
import unittest
from singer import metadata

from tap_oracle_fusion.schema import (
    DATASTORE_KEY_METADATA_KEY,
    ENTITY_SET_METADATA_KEY,
    _attribute_name,
    _attribute_type,
    _coerce_attribute_payload,
    _extract_attributes,
    _is_datetime_field,
    _is_datetime_type,
    _merge_types,
    _normalize_type_name,
    _observed_json_type,
    build_bicc_schema,
    build_bicc_schema_and_metadata,
    build_metadata,
    build_schema,
    build_schema_and_metadata,
    enrich_schema_with_samples,
    infer_bicc_primary_keys,
    infer_bicc_replication_key,
    infer_primary_key,
    infer_replication_key,
    oracle_attribute_to_property_schema,
)


class TestNormalizeTypeName(unittest.TestCase):
    def test_strips_and_lowercases(self):
        self.assertEqual(_normalize_type_name("  String  "), "string")
        self.assertEqual(_normalize_type_name("VARCHAR"), "varchar")

    def test_none_returns_empty(self):
        self.assertEqual(_normalize_type_name(None), "")

    def test_empty_returns_empty(self):
        self.assertEqual(_normalize_type_name(""), "")


class TestIsDatetimeType(unittest.TestCase):
    def test_datetime_types(self):
        for t in ("date", "datetime", "timestamp", "time", "offsetdatetime"):
            self.assertTrue(_is_datetime_type(t), f"expected {t!r} to be datetime type")

    def test_non_datetime_types(self):
        for t in ("string", "integer", "number", "boolean"):
            self.assertFalse(_is_datetime_type(t))


class TestIsDatetimeField(unittest.TestCase):
    def test_datetime_oracle_type_true(self):
        self.assertTrue(_is_datetime_field("SomeField", "date"))
        self.assertTrue(_is_datetime_field("SomeField", "timestamp"))

    def test_field_name_ends_with_date(self):
        self.assertTrue(_is_datetime_field("LastUpdateDate", "string"))

    def test_field_name_ends_with_time(self):
        self.assertTrue(_is_datetime_field("CreatedTime", "string"))

    def test_field_name_ends_with_datetime(self):
        self.assertTrue(_is_datetime_field("UpdatedDateTime", "string"))

    def test_field_name_ends_with_underscore_date(self):
        self.assertTrue(_is_datetime_field("start_date", "string"))

    def test_field_name_ends_with_underscore_time(self):
        self.assertTrue(_is_datetime_field("end_time", "string"))

    def test_no_match_returns_false(self):
        self.assertFalse(_is_datetime_field("WorkerId", "string"))


class TestOracleAttributeToPropertySchema(unittest.TestCase):
    def test_string_type(self):
        schema = oracle_attribute_to_property_schema({"type": "string"})
        self.assertEqual(schema["type"], ["null", "string"])
        self.assertNotIn("format", schema)

    def test_varchar_type(self):
        schema = oracle_attribute_to_property_schema({"type": "varchar"})
        self.assertEqual(schema["type"], ["null", "string"])

    def test_integer_type(self):
        schema = oracle_attribute_to_property_schema({"type": "integer"})
        self.assertEqual(schema["type"], ["null", "integer"])

    def test_long_type(self):
        schema = oracle_attribute_to_property_schema({"type": "long"})
        self.assertEqual(schema["type"], ["null", "integer"])

    def test_number_type(self):
        schema = oracle_attribute_to_property_schema({"type": "number"})
        self.assertEqual(schema["type"], ["null", "number"])

    def test_decimal_type(self):
        schema = oracle_attribute_to_property_schema({"type": "decimal"})
        self.assertEqual(schema["type"], ["null", "number"])

    def test_boolean_type(self):
        schema = oracle_attribute_to_property_schema({"type": "boolean"})
        self.assertEqual(schema["type"], ["null", "boolean"])

    def test_array_type(self):
        schema = oracle_attribute_to_property_schema({"type": "array"})
        self.assertEqual(schema["type"], ["null", "array"])
        self.assertIn("items", schema)

    def test_list_type(self):
        schema = oracle_attribute_to_property_schema({"type": "list"})
        self.assertEqual(schema["type"], ["null", "array"])

    def test_object_type(self):
        schema = oracle_attribute_to_property_schema({"type": "object"})
        self.assertEqual(schema["type"], ["null", "object"])
        self.assertTrue(schema.get("additionalProperties"))

    def test_record_type(self):
        schema = oracle_attribute_to_property_schema({"type": "record"})
        self.assertEqual(schema["type"], ["null", "object"])

    def test_map_type(self):
        schema = oracle_attribute_to_property_schema({"type": "map"})
        self.assertEqual(schema["type"], ["null", "object"])

    def test_unknown_type_defaults_to_string(self):
        schema = oracle_attribute_to_property_schema({"type": "exotic_type"})
        self.assertEqual(schema["type"], ["null", "string"])

    def test_date_type_has_format(self):
        schema = oracle_attribute_to_property_schema({"type": "date"})
        self.assertEqual(schema.get("format"), "date-time")

    def test_timestamp_type_has_format(self):
        schema = oracle_attribute_to_property_schema({"type": "timestamp"})
        self.assertEqual(schema.get("format"), "date-time")


class TestCoerceAttributePayload(unittest.TestCase):
    def test_uses_columns_key(self):
        entry = {"columns": [{"name": "Id"}, {"name": "Name"}]}
        result = _coerce_attribute_payload(entry)
        self.assertEqual(len(result), 2)

    def test_uses_attributes_key(self):
        entry = {"attributes": [{"name": "Id"}]}
        result = _coerce_attribute_payload(entry)
        self.assertEqual(len(result), 1)

    def test_uses_fields_key(self):
        entry = {"fields": [{"name": "Id"}]}
        result = _coerce_attribute_payload(entry)
        self.assertEqual(len(result), 1)

    def test_uses_datastoreColumns_key(self):
        entry = {"datastoreColumns": [{"name": "Id"}]}
        result = _coerce_attribute_payload(entry)
        self.assertEqual(len(result), 1)

    def test_non_mapping_returns_empty(self):
        self.assertEqual(_coerce_attribute_payload(["not", "a", "mapping"]), [])

    def test_no_known_key_returns_empty(self):
        self.assertEqual(_coerce_attribute_payload({"other": [{"name": "Id"}]}), [])

    def test_filters_non_mapping_values(self):
        entry = {"columns": [{"name": "Id"}, "not_a_mapping", 42]}
        result = _coerce_attribute_payload(entry)
        self.assertEqual(len(result), 1)


class TestAttributeName(unittest.TestCase):
    def test_name_key(self):
        self.assertEqual(_attribute_name({"name": "WorkerId"}), "WorkerId")

    def test_columnName_key(self):
        self.assertEqual(_attribute_name({"columnName": "WorkerId"}), "WorkerId")

    def test_attributeName_key(self):
        self.assertEqual(_attribute_name({"attributeName": "WorkerId"}), "WorkerId")

    def test_fieldName_key(self):
        self.assertEqual(_attribute_name({"fieldName": "WorkerId"}), "WorkerId")

    def test_strips_whitespace(self):
        self.assertEqual(_attribute_name({"name": "  Id  "}), "Id")

    def test_returns_none_when_no_valid_key(self):
        self.assertIsNone(_attribute_name({"other": "something"}))

    def test_returns_none_for_empty_string(self):
        self.assertIsNone(_attribute_name({"name": ""}))


class TestAttributeType(unittest.TestCase):
    def test_type_key(self):
        self.assertEqual(_attribute_type({"type": "string"}), "string")

    def test_dataType_key(self):
        self.assertEqual(_attribute_type({"dataType": "integer"}), "integer")

    def test_columnType_key(self):
        self.assertEqual(_attribute_type({"columnType": "datetime"}), "datetime")

    def test_default_string_when_no_key(self):
        self.assertEqual(_attribute_type({"other": "something"}), "string")

    def test_strips_whitespace(self):
        self.assertEqual(_attribute_type({"type": "  date  "}), "date")


class TestInferBiccPrimaryKeys(unittest.TestCase):
    def test_single_pk(self):
        attrs = [
            {"columnName": "SetId", "isPrimaryKey": True},
            {"columnName": "Name", "isPrimaryKey": False},
        ]
        self.assertEqual(infer_bicc_primary_keys(attrs), ["SetId"])

    def test_composite_pk(self):
        attrs = [
            {"columnName": "SetId", "isPrimaryKey": True},
            {"columnName": "ItemId", "isPrimaryKey": True},
        ]
        self.assertEqual(infer_bicc_primary_keys(attrs), ["SetId", "ItemId"])

    def test_deduplicates_repeated_pk(self):
        attrs = [
            {"columnName": "SetId", "isPrimaryKey": True},
            {"columnName": "SetId", "isPrimaryKey": True},
        ]
        self.assertEqual(infer_bicc_primary_keys(attrs), ["SetId"])

    def test_no_pk_returns_empty(self):
        attrs = [{"columnName": "Name", "isPrimaryKey": False}]
        self.assertEqual(infer_bicc_primary_keys(attrs), [])

    def test_skips_unnamed_attributes(self):
        attrs = [{"isPrimaryKey": True}, {"columnName": "Id", "isPrimaryKey": True}]
        self.assertEqual(infer_bicc_primary_keys(attrs), ["Id"])


class TestInferBiccReplicationKey(unittest.TestCase):
    def test_isLastUpdateDate(self):
        attrs = [
            {"columnName": "SomeField"},
            {"columnName": "LastUpdateDate", "isLastUpdateDate": True},
        ]
        self.assertEqual(infer_bicc_replication_key(attrs), "LastUpdateDate")

    def test_isCreationDate_fallback(self):
        attrs = [
            {"columnName": "CreatedOn", "isCreationDate": True},
        ]
        self.assertEqual(infer_bicc_replication_key(attrs), "CreatedOn")

    def test_returns_none_when_no_match(self):
        attrs = [{"columnName": "WorkerId"}]
        self.assertIsNone(infer_bicc_replication_key(attrs))

    def test_prefers_last_update_over_creation(self):
        attrs = [
            {"columnName": "CreatedOn", "isCreationDate": True},
            {"columnName": "UpdatedOn", "isLastUpdateDate": True},
        ]
        self.assertEqual(infer_bicc_replication_key(attrs), "UpdatedOn")


class TestBuildBiccSchema(unittest.TestCase):
    def test_builds_from_columns(self):
        entry = {"columns": [{"columnName": "WorkerId", "dataType": "string"}]}
        schema = build_bicc_schema(entry)
        self.assertIn("WorkerId", schema["properties"])

    def test_empty_columns_adds_additional_properties(self):
        schema = build_bicc_schema({})
        self.assertTrue(schema.get("additionalProperties"))

    def test_skips_columns_without_name(self):
        entry = {"columns": [{"dataType": "string"}]}
        schema = build_bicc_schema(entry)
        self.assertEqual(schema.get("properties", {}), {})
        self.assertTrue(schema.get("additionalProperties"))


class TestBuildBiccSchemaAndMetadataNoReplicationKey(unittest.TestCase):
    def test_full_table_when_no_replication_key(self):
        entry = {
            "columns": [
                {"columnName": "SetId", "dataType": "string", "isPrimaryKey": True},
            ]
        }
        schema_dict, mdata, pks = build_bicc_schema_and_metadata(
            entry, "biacm/rest/meta/datastores/MyStore", "MyStore"
        )
        mdata_map = metadata.to_map(mdata)
        self.assertEqual(mdata_map[()].get("forced-replication-method"), "FULL_TABLE")
        self.assertEqual(pks, ["SetId"])

    def test_incremental_when_replication_key_present(self):
        entry = {
            "columns": [
                {"columnName": "Id", "dataType": "string", "isPrimaryKey": True},
                {"columnName": "LastUpdateDate", "dataType": "timestamp", "isLastUpdateDate": True},
            ]
        }
        _, mdata, _ = build_bicc_schema_and_metadata(
            entry, "biacm/rest/meta/datastores/MyStore", "MyStore"
        )
        mdata_map = metadata.to_map(mdata)
        self.assertEqual(mdata_map[()].get("forced-replication-method"), "INCREMENTAL")

    def test_entity_set_and_datastore_key_in_metadata(self):
        entry = {"columns": [{"columnName": "Id", "dataType": "string"}]}
        _, mdata, _ = build_bicc_schema_and_metadata(
            entry, "biacm/rest/meta/datastores/FscmTopModelAM.Worker", "FscmTopModelAM.Worker"
        )
        mdata_map = metadata.to_map(mdata)
        self.assertEqual(
            mdata_map[()].get(ENTITY_SET_METADATA_KEY),
            "biacm/rest/meta/datastores/FscmTopModelAM.Worker",
        )
        self.assertEqual(
            mdata_map[()].get(DATASTORE_KEY_METADATA_KEY),
            "FscmTopModelAM.Worker",
        )


class TestExtractAttributes(unittest.TestCase):
    def test_extracts_from_resources_mapping(self):
        payload = {
            "Resources": {
                "Workers": {
                    "attributes": [{"name": "WorkerId"}, {"name": "Name"}]
                }
            }
        }
        attrs = _extract_attributes(payload, "Workers")
        self.assertEqual(len(attrs), 2)

    def test_case_insensitive_resource_lookup(self):
        payload = {
            "Resources": {
                "workers": {"attributes": [{"name": "WorkerId"}]}
            }
        }
        attrs = _extract_attributes(payload, "Workers")
        self.assertEqual(len(attrs), 1)

    def test_falls_back_to_top_level_attributes(self):
        payload = {"attributes": [{"name": "Id"}, {"name": "Name"}]}
        attrs = _extract_attributes(payload, "SomeName")
        self.assertEqual(len(attrs), 2)

    def test_returns_empty_for_empty_payload(self):
        self.assertEqual(_extract_attributes({}, "SomeName"), [])

    def test_filters_non_mapping_attributes(self):
        payload = {"attributes": [{"name": "Id"}, "not_a_mapping"]}
        attrs = _extract_attributes(payload, "SomeName")
        self.assertEqual(len(attrs), 1)


class TestInferPrimaryKey(unittest.TestCase):
    def test_finder_based_pk(self):
        payload = {
            "Resources": {
                "Workers": {
                    "collection": {
                        "finders": [
                            {
                                "name": "PrimaryKey",
                                "attributes": [{"name": "WorkerId"}],
                            }
                        ]
                    }
                }
            }
        }
        attrs = [{"name": "WorkerId"}]
        pk = infer_primary_key("Workers", payload, attrs)
        self.assertEqual(pk, "WorkerId")

    def test_id_fallback(self):
        payload = {}
        attrs = [{"name": "SomeName"}, {"name": "WorkerId"}]
        pk = infer_primary_key("Workers", payload, attrs)
        self.assertEqual(pk, "WorkerId")

    def test_exact_id_match(self):
        payload = {}
        attrs = [{"name": "Id"}, {"name": "Name"}]
        pk = infer_primary_key("Workers", payload, attrs)
        self.assertEqual(pk, "Id")

    def test_returns_none_when_no_match(self):
        payload = {}
        attrs = [{"name": "Name"}, {"name": "Description"}]
        pk = infer_primary_key("Workers", payload, attrs)
        self.assertIsNone(pk)

    def test_skips_non_primarykey_finders(self):
        payload = {
            "Resources": {
                "Workers": {
                    "collection": {
                        "finders": [
                            {"name": "ByName", "attributes": [{"name": "Name"}]},
                        ]
                    }
                }
            }
        }
        attrs = [{"name": "WorkerId"}]
        # No PrimaryKey finder → falls back to id-like attr
        pk = infer_primary_key("Workers", payload, attrs)
        self.assertEqual(pk, "WorkerId")

    def test_handles_non_mapping_finders(self):
        payload = {
            "Resources": {
                "Workers": {
                    "collection": {
                        "finders": ["not_a_mapping"]
                    }
                }
            }
        }
        attrs = [{"name": "WorkerId"}]
        pk = infer_primary_key("Workers", payload, attrs)
        self.assertEqual(pk, "WorkerId")


class TestInferReplicationKey(unittest.TestCase):
    def test_last_update_date_candidate(self):
        attrs = [{"name": "LastUpdateDate", "type": "string"}]
        self.assertEqual(infer_replication_key(attrs), "LastUpdateDate")

    def test_creation_date_candidate(self):
        attrs = [{"name": "CreationDate", "type": "string"}]
        self.assertEqual(infer_replication_key(attrs), "CreationDate")

    def test_datetime_type_fallback(self):
        attrs = [{"name": "SomeTimestamp", "type": "datetime", "queryable": True}]
        self.assertEqual(infer_replication_key(attrs), "SomeTimestamp")

    def test_returns_none_when_no_match(self):
        attrs = [{"name": "WorkerId", "type": "string"}]
        self.assertIsNone(infer_replication_key(attrs))

    def test_prefers_candidate_list_over_datetime_type(self):
        attrs = [
            {"name": "SomeTimestamp", "type": "datetime"},
            {"name": "LastUpdateDate", "type": "string"},
        ]
        self.assertEqual(infer_replication_key(attrs), "LastUpdateDate")


class TestBuildSchema(unittest.TestCase):
    def test_builds_properties(self):
        attrs = [
            {"name": "WorkerId", "type": "string"},
            {"name": "Amount", "type": "number"},
        ]
        schema = build_schema(attrs)
        self.assertIn("WorkerId", schema["properties"])
        self.assertIn("Amount", schema["properties"])
        self.assertEqual(schema["properties"]["WorkerId"]["type"], ["null", "string"])
        self.assertEqual(schema["properties"]["Amount"]["type"], ["null", "number"])

    def test_skips_attributes_without_name(self):
        attrs = [{"type": "string"}, {"name": "Id", "type": "string"}]
        schema = build_schema(attrs)
        self.assertEqual(list(schema["properties"].keys()), ["Id"])

    def test_skips_non_string_names(self):
        attrs = [{"name": 123, "type": "string"}, {"name": "Id", "type": "string"}]
        schema = build_schema(attrs)
        self.assertEqual(list(schema["properties"].keys()), ["Id"])


class TestExtractAttributesReturnEmpty(unittest.TestCase):
    def test_returns_empty_when_attributes_is_not_a_list(self):
        # Resources exist but attributes is a dict, not list → fall through to return []
        payload = {
            "Resources": {
                "Workers": {"attributes": {"not": "a-list"}}
            },
            "attributes": {"also": "not-a-list"},
        }
        result = _extract_attributes(payload, "Workers")
        self.assertEqual(result, [])


class TestObservedJsonType(unittest.TestCase):
    def test_none_returns_null(self):
        self.assertEqual(_observed_json_type(None), "null")

    def test_bool_returns_boolean(self):
        self.assertEqual(_observed_json_type(True), "boolean")
        self.assertEqual(_observed_json_type(False), "boolean")

    def test_int_returns_integer(self):
        self.assertEqual(_observed_json_type(42), "integer")

    def test_float_returns_number(self):
        self.assertEqual(_observed_json_type(3.14), "number")

    def test_dict_returns_object(self):
        self.assertEqual(_observed_json_type({"key": "val"}), "object")

    def test_list_returns_array(self):
        self.assertEqual(_observed_json_type([1, 2, 3]), "array")

    def test_string_returns_string(self):
        self.assertEqual(_observed_json_type("hello"), "string")


class TestMergeTypes(unittest.TestCase):
    def test_adds_new_type(self):
        result = _merge_types(["null", "string"], "integer")
        self.assertIn("integer", result)
        self.assertIn("null", result)

    def test_integer_superseded_by_number(self):
        result = _merge_types(["null", "integer"], "number")
        self.assertIn("number", result)
        self.assertNotIn("integer", result)

    def test_preserves_order(self):
        result = _merge_types(["null"], "string")
        self.assertEqual(result.index("null"), 0)

    def test_no_duplicates(self):
        result = _merge_types(["null", "string"], "string")
        self.assertEqual(result.count("string"), 1)


class TestEnrichSchemaWithSamples(unittest.TestCase):
    def test_adds_new_properties_from_samples(self):
        schema = {"properties": {}}
        samples = [{"id": 1, "name": "Alice"}, {"id": 2, "active": True}]
        result = enrich_schema_with_samples(schema, samples)
        self.assertIn("id", result["properties"])
        self.assertIn("name", result["properties"])
        self.assertIn("active", result["properties"])

    def test_merges_types_for_existing_properties(self):
        schema = {"properties": {"id": {"type": ["null", "string"]}}}
        samples = [{"id": 42}]
        result = enrich_schema_with_samples(schema, samples)
        types = result["properties"]["id"]["type"]
        self.assertIn("integer", types)

    def test_skips_non_mapping_records(self):
        schema = {"properties": {}}
        result = enrich_schema_with_samples(schema, ["not-a-mapping", 42])
        self.assertEqual(result["properties"], {})

    def test_creates_properties_if_missing(self):
        schema = {}
        result = enrich_schema_with_samples(schema, [{"key": "val"}])
        self.assertIn("key", result["properties"])


class TestBuildMetadata(unittest.TestCase):
    def test_incremental_when_replication_key(self):
        schema = {"type": "object", "properties": {"Id": {}, "UpdatedAt": {}}}
        mdata = build_metadata(schema, primary_key="Id", replication_key="UpdatedAt")
        mdata_map = metadata.to_map(mdata)
        self.assertEqual(mdata_map[()].get("forced-replication-method"), "INCREMENTAL")
        self.assertEqual(mdata_map[()].get("valid-replication-keys"), ["UpdatedAt"])
        self.assertEqual(
            mdata_map[("properties", "UpdatedAt")].get("inclusion"), "automatic"
        )

    def test_full_table_without_replication_key(self):
        schema = {"type": "object", "properties": {"Id": {}}}
        mdata = build_metadata(schema, primary_key="Id", replication_key=None)
        mdata_map = metadata.to_map(mdata)
        self.assertEqual(mdata_map[()].get("forced-replication-method"), "FULL_TABLE")

    def test_no_primary_key(self):
        schema = {"type": "object", "properties": {"Name": {}}}
        mdata = build_metadata(schema, primary_key=None, replication_key=None)
        mdata_map = metadata.to_map(mdata)
        self.assertEqual(mdata_map[()].get("table-key-properties"), [])


class TestBuildSchemaAndMetadata(unittest.TestCase):
    def test_builds_schema_and_metadata_from_describe(self):
        payload = {
            "Resources": {
                "Workers": {
                    "attributes": [
                        {"name": "WorkerId", "type": "string"},
                        {"name": "LastUpdateDate", "type": "datetime"},
                    ],
                    "collection": {
                        "finders": [
                            {"name": "PrimaryKey", "attributes": [{"name": "WorkerId"}]}
                        ]
                    },
                }
            }
        }
        schema, mdata, pk, rk = build_schema_and_metadata("Workers", payload)
        self.assertIn("WorkerId", schema["properties"])
        self.assertEqual(pk, "WorkerId")
        self.assertEqual(rk, "LastUpdateDate")
        mdata_map = metadata.to_map(mdata)
        self.assertEqual(mdata_map[()].get("forced-replication-method"), "INCREMENTAL")

    def test_enriches_with_sample_records(self):
        payload = {"attributes": [{"name": "Id", "type": "string"}]}
        samples = [{"Id": "1", "ExtraField": 42}]
        schema, _mdata, _pk, _rk = build_schema_and_metadata(
            "Resource", payload, sample_records=samples
        )
        self.assertIn("ExtraField", schema["properties"])

    def test_adds_pk_to_schema_if_missing(self):
        """If the PK is inferred but not present in schema properties, it is added."""
        payload = {
            "Resources": {
                "Items": {
                    "attributes": [{"name": "Name", "type": "string"}],
                    "collection": {
                        "finders": [
                            {"name": "PrimaryKey", "attributes": [{"name": "ItemId"}]}
                        ]
                    },
                }
            }
        }
        schema, _mdata, pk, _rk = build_schema_and_metadata("Items", payload)
        self.assertEqual(pk, "ItemId")
        self.assertIn("ItemId", schema["properties"])


if __name__ == "__main__":
    unittest.main()
