import importlib
import unittest
from unittest import mock

from singer.catalog import Schema
from singer import metadata

discover_module = importlib.import_module("tap_oracle_fusion.discover")
schema_module = importlib.import_module("tap_oracle_fusion.schema")


class TestDiscoverHelpers(unittest.TestCase):
    def test_extract_datastore_entries_prefers_datastores_key(self):
        payload = {
            "dataStores": ["Worker", "Department"],
            "items": ["Fallback"],
        }

        entries = discover_module._extract_datastore_entries(payload)
        self.assertEqual(entries, ["Worker", "Department"])

    def test_extract_datastore_name_from_string_and_mapping(self):
        self.assertEqual(discover_module._extract_datastore_name("Worker"), "Worker")
        self.assertEqual(
            discover_module._extract_datastore_name({"datastoreName": "Department"}),
            "Department",
        )

    def test_build_schema_for_datastore_uses_columns(self):
        entry = {
            "name": "Worker",
            "columns": [
                {"columnName": "WorkerId", "dataType": "string"},
                {"columnName": "LastUpdateDate", "dataType": "datetime"},
            ],
        }
        schema = schema_module.build_bicc_schema(entry)
        self.assertIn("WorkerId", schema["properties"])
        self.assertEqual(
            schema["properties"]["LastUpdateDate"].get("format"),
            "date-time",
        )

    def test_build_schema_for_varchar_date_named_column_does_not_force_datetime(self):
        entry = {
            "name": "StandardHeaderPVO",
            "columns": [
                {
                    "columnName": "POSystemParametersDefaultPromiseDate",
                    "dataType": "VARCHAR",
                },
            ],
        }

        schema = schema_module.build_bicc_schema(entry)

        self.assertEqual(
            schema["properties"]["POSystemParametersDefaultPromiseDate"]["type"],
            ["null", "string"],
        )
        self.assertNotIn(
            "format",
            schema["properties"]["POSystemParametersDefaultPromiseDate"],
        )

    def test_build_schema_for_numeric_column_uses_number_type(self):
        entry = {
            "name": "StandardHeaderPVO",
            "columns": [
                {
                    "columnName": "POSystemParametersDoctypeId",
                    "dataType": "NUMERIC",
                },
            ],
        }

        schema = schema_module.build_bicc_schema(entry)

        self.assertEqual(
            schema["properties"]["POSystemParametersDoctypeId"]["type"],
            ["null", "number"],
        )

    def test_build_bicc_schema_metadata_preserves_composite_primary_keys(self):
        entry = {
            "columns": [
                {"columnName": "SetId", "dataType": "string", "isPrimaryKey": True},
                {"columnName": "ItemId", "dataType": "string", "isPrimaryKey": True},
                {"columnName": "LastUpdateDate", "dataType": "timestamp", "isLastUpdateDate": True},
            ]
        }

        _, mdata, primary_keys = schema_module.build_bicc_schema_and_metadata(
            entry,
            "biacm/rest/meta/datastores/FscmTopModelAM.CompositeKeyStore",
            "FscmTopModelAM.CompositeKeyStore",
        )

        self.assertEqual(primary_keys, ["SetId", "ItemId"])
        self.assertEqual(
            metadata.to_map(mdata)[()].get("table-key-properties"),
            ["SetId", "ItemId"],
        )


class TestDiscoverFlow(unittest.TestCase):
    @mock.patch("tap_oracle_fusion.discover.OracleClient")
    def test_get_stream_resource_map_uses_configured_datastores(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client_cls.parse_next_link.return_value = None
        mock_client.get.return_value = {
            "dataStores": [
                "Worker",
                "Department",
                "Worker Assignments",
            ]
        }

        config = {
            "base_url": "https://example",
            "datastores": ["Worker", "Worker Assignments"],
        }

        stream_map = discover_module.get_stream_resource_map(config)

        self.assertEqual(
            stream_map,
            {
                "worker": "biacm/rest/meta/datastores/Worker",
                "worker_assignments": "biacm/rest/meta/datastores/Worker%20Assignments",
            },
        )
        mock_client.get.assert_called_once_with("biacm/rest/meta/datastores", params={"limit": 500, "offset": 0})
        mock_client_cls.assert_called_once_with(config)

    @mock.patch("tap_oracle_fusion.discover.OracleClient")
    def test_discover_builds_catalog_entries_with_deduped_streams(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client_cls.parse_next_link.return_value = None

        def _get_side_effect(path, params=None):
            if path == "biacm/rest/meta/datastores":
                return {"dataStores": ["Worker", "worker"]}
            if path == "biacm/rest/meta/datastores/Worker":
                return {
                    "columns": [
                        {"columnName": "WorkerId", "dataType": "string", "isPrimaryKey": True},
                        {"columnName": "LastUpdateDate", "dataType": "timestamp", "isLastUpdateDate": True},
                    ]
                }
            raise AssertionError(f"Unexpected path: {path} params={params}")

        mock_client.get.side_effect = _get_side_effect

        config = {
            "base_url": "https://example",
            "datastores": ["Worker", "worker"],
        }

        catalog = discover_module.discover(config)

        self.assertEqual(len(catalog.streams), 1)
        entry = catalog.streams[0]
        self.assertEqual(entry.stream, "worker")
        self.assertEqual(entry.tap_stream_id, "worker")
        self.assertEqual(entry.key_properties, ["WorkerId"])
        self.assertIsInstance(entry.schema, Schema)

        mdata = metadata.to_map(entry.metadata)
        self.assertEqual(
            mdata[()].get(schema_module.ENTITY_SET_METADATA_KEY),
            "biacm/rest/meta/datastores/Worker",
        )
        self.assertEqual(mdata[()].get("valid-replication-keys"), ["LastUpdateDate"])

    @mock.patch("tap_oracle_fusion.discover.OracleClient")
    def test_discover_applies_discovery_limit(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client_cls.parse_next_link.return_value = None

        def _get_side_effect(path, params=None):
            if path == "biacm/rest/meta/datastores":
                return {"dataStores": ["A.Store", "B.Store", "C.Store"]}
            return {"columns": [{"columnName": "Id", "dataType": "string"}]}

        mock_client.get.side_effect = _get_side_effect

        catalog = discover_module.discover(
            {
                "base_url": "https://example",
                "discovery_limit": 2,
            }
        )

        self.assertEqual(len(catalog.streams), 2)
        discovered_names = {stream.tap_stream_id for stream in catalog.streams}
        self.assertEqual(discovered_names, {"a_store", "b_store"})

    @mock.patch("tap_oracle_fusion.discover.OracleClient")
    def test_discover_skips_datastore_without_schema(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client_cls.parse_next_link.return_value = None

        def _get_side_effect(path, params=None):
            if path == "biacm/rest/meta/datastores":
                return {"dataStores": ["Accessible.Store", "Inaccessible.Store"]}
            if path == "biacm/rest/meta/datastores/Accessible.Store":
                return {"columns": [{"columnName": "Id", "dataType": "string"}]}
            if path == "biacm/rest/meta/datastores/Inaccessible.Store":
                return {}
            raise AssertionError(f"Unexpected path: {path} params={params}")

        mock_client.get.side_effect = _get_side_effect

        catalog = discover_module.discover({"base_url": "https://example"})

        self.assertEqual(len(catalog.streams), 1)
        self.assertEqual(catalog.streams[0].tap_stream_id, "accessible_store")

    @mock.patch("tap_oracle_fusion.discover.LOGGER")
    @mock.patch("tap_oracle_fusion.discover.OracleClient")
    def test_discover_logs_skipped_datastore_summary(self, mock_client_cls, mock_logger):
        mock_client = mock_client_cls.return_value
        mock_client_cls.parse_next_link.return_value = None

        def _get_side_effect(path, params=None):
            if path == "biacm/rest/meta/datastores":
                return {"dataStores": ["Accessible.Store", "Inaccessible.Store"]}
            if path == "biacm/rest/meta/datastores/Accessible.Store":
                return {"columns": [{"columnName": "Id", "dataType": "string"}]}
            if path == "biacm/rest/meta/datastores/Inaccessible.Store":
                return {}
            raise AssertionError(f"Unexpected path: {path} params={params}")

        mock_client.get.side_effect = _get_side_effect

        discover_module.discover({"base_url": "https://example", "discovery_workers": 1})

        self.assertEqual(len(mock_logger.warning.call_args_list), 1)
        self.assertEqual(
            mock_logger.warning.call_args_list[0],
            mock.call(
                "Excluding %s datastore(s) from catalog: %s",
                1,
                "Inaccessible.Store",
            ),
        )

    @mock.patch("tap_oracle_fusion.discover.OracleClient")
    def test_get_stream_resource_map_applies_parent_filter(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client_cls.parse_next_link.return_value = None
        mock_client.get.return_value = {
            "dataStores": [
                "FscmTopModelAM.Worker",
                "CrmAnalyticsAM.Opportunity",
                "HcmTopModelAnalyticsGlobalAM.Absence",
            ]
        }

        config = {
            "base_url": "https://example",
            "discovery_parents": ["FscmTopModelAM", "HcmTopModelAnalyticsGlobalAM"],
        }

        stream_map = discover_module.get_stream_resource_map(config)

        self.assertEqual(
            stream_map,
            {
                "fscmtopmodelam_worker": "biacm/rest/meta/datastores/FscmTopModelAM.Worker",
                "hcmtopmodelanalyticsglobalam_absence": "biacm/rest/meta/datastores/HcmTopModelAnalyticsGlobalAM.Absence",
            },
        )

    @mock.patch("tap_oracle_fusion.discover.OracleClient")
    def test_discover_parents_and_datastores_use_intersection(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client_cls.parse_next_link.return_value = None

        def _get_side_effect(path, params=None):
            if path == "biacm/rest/meta/datastores":
                return {
                    "dataStores": [
                        "FscmTopModelAM.Target",
                        "FscmTopModelAM.Other",
                        "CrmAnalyticsAM.Target",
                    ]
                }
            return {"columns": [{"columnName": "Id", "dataType": "string"}]}

        mock_client.get.side_effect = _get_side_effect

        catalog = discover_module.discover(
            {
                "base_url": "https://example",
                "discovery_parents": ["FscmTopModelAM"],
                "datastores": ["FscmTopModelAM.Target", "CrmAnalyticsAM.Target"],
            }
        )

        self.assertEqual(len(catalog.streams), 1)
        self.assertEqual(catalog.streams[0].tap_stream_id, "fscmtopmodelam_target")


if __name__ == "__main__":
    unittest.main()
