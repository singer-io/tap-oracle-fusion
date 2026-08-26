"""Extended tests for tap_oracle_fusion.discover module — helper functions."""
import importlib
import unittest
from unittest import mock

discover_module = importlib.import_module("tap_oracle_fusion.discover")


class TestIterConfiguredDatastores(unittest.TestCase):
    def test_list_of_strings(self):
        config = {"datastores": ["Worker", "Department"]}
        result = list(discover_module._iter_configured_datastores(config))
        self.assertEqual(result, ["Worker", "Department"])

    def test_list_of_mappings(self):
        config = {"datastores": [{"name": "Worker"}, {"datastore": "Department"}]}
        result = list(discover_module._iter_configured_datastores(config))
        self.assertEqual(result, ["Worker", "Department"])

    def test_mapping_with_resource_key(self):
        config = {"datastores": [{"resource": "Items"}]}
        result = list(discover_module._iter_configured_datastores(config))
        self.assertEqual(result, ["Items"])

    def test_mapping_without_name_skipped(self):
        config = {"datastores": [{"other": "value"}]}
        result = list(discover_module._iter_configured_datastores(config))
        self.assertEqual(result, [])

    def test_streams_key_used(self):
        config = {"streams": ["Worker"]}
        result = list(discover_module._iter_configured_datastores(config))
        self.assertEqual(result, ["Worker"])

    def test_empty_config_returns_empty(self):
        result = list(discover_module._iter_configured_datastores({}))
        self.assertEqual(result, [])


class TestIterConfiguredParents(unittest.TestCase):
    def test_none_returns_empty(self):
        result = list(discover_module._iter_configured_parents({}))
        self.assertEqual(result, [])

    def test_string_splits_by_comma(self):
        config = {"discovery_parents": "FscmTopModelAM, HcmTopModelAM"}
        result = list(discover_module._iter_configured_parents(config))
        self.assertEqual(result, ["FscmTopModelAM", "HcmTopModelAM"])

    def test_list_of_strings(self):
        config = {"discovery_parents": ["FscmTopModelAM", "HcmTopModelAM"]}
        result = list(discover_module._iter_configured_parents(config))
        self.assertEqual(result, ["FscmTopModelAM", "HcmTopModelAM"])

    def test_set_of_strings(self):
        config = {"discovery_parents": {"FscmTopModelAM"}}
        result = list(discover_module._iter_configured_parents(config))
        self.assertEqual(result, ["FscmTopModelAM"])

    def test_discovery_parents_key_used(self):
        config = {"discovery_parents": ["FscmTopModelAM"]}
        result = list(discover_module._iter_configured_parents(config))
        self.assertEqual(result, ["FscmTopModelAM"])

    def test_other_type_returns_empty(self):
        config = {"discovery_parents": 42}
        result = list(discover_module._iter_configured_parents(config))
        self.assertEqual(result, [])

    def test_skips_non_string_items_in_list(self):
        config = {"discovery_parents": ["FscmTopModelAM", 123, None]}
        result = list(discover_module._iter_configured_parents(config))
        self.assertEqual(result, ["FscmTopModelAM"])


class TestGetDiscoveryWorkers(unittest.TestCase):
    def test_invalid_auto_falls_back_to_default(self):
        config = {"discovery_workers": "auto"}
        result = discover_module._get_discovery_workers(config)
        self.assertEqual(result, discover_module.DISCOVERY_WORKER_KEYS[1])

    def test_integer_value(self):
        config = {"discovery_workers": 4}
        result = discover_module._get_discovery_workers(config)
        self.assertEqual(result, 4)

    def test_invalid_string_falls_back_to_default(self):
        config = {"discovery_workers": "not-a-number"}
        result = discover_module._get_discovery_workers(config)
        self.assertEqual(result, discover_module.DISCOVERY_WORKER_KEYS[1])

    def test_zero_falls_back_to_default(self):
        config = {"discovery_workers": 0}
        result = discover_module._get_discovery_workers(config)
        self.assertEqual(result, discover_module.DISCOVERY_WORKER_KEYS[1])

    def test_large_value_returned_as_is(self):
        config = {"discovery_workers": 9999}
        result = discover_module._get_discovery_workers(config)
        self.assertEqual(result, 9999)


class TestListDatastores(unittest.TestCase):
    @mock.patch("tap_oracle_fusion.discover.OracleClient")
    def test_single_request_returns_all_entries(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.get.return_value = {"dataStores": ["A.Store", "B.Store"]}

        entries = discover_module._list_datastores(mock_client)
        self.assertEqual(entries, ["A.Store", "B.Store"])
        mock_client.get.assert_called_once()


class TestListDiscoveryCandidates(unittest.TestCase):
    @mock.patch("tap_oracle_fusion.discover.OracleClient")
    def test_filters_by_parent(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client_cls.parse_next_link.return_value = None
        mock_client.get.return_value = {
            "dataStores": [
                "FscmTopModelAM.Worker",
                "CrmAnalyticsAM.Opportunity",
            ]
        }

        config = {
            "base_url": "https://example",
            "discovery_parents": ["FscmTopModelAM"],
        }
        candidates = discover_module._list_discovery_candidates(mock_client, config)
        self.assertEqual(candidates, ["FscmTopModelAM.Worker"])

    @mock.patch("tap_oracle_fusion.discover.OracleClient")
    def test_deduplicates_case_insensitive(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client_cls.parse_next_link.return_value = None
        mock_client.get.return_value = {"dataStores": ["Worker", "WORKER", "worker"]}

        candidates = discover_module._list_discovery_candidates(mock_client, {})
        self.assertEqual(len(candidates), 1)

    @mock.patch("tap_oracle_fusion.discover.OracleClient")
    def test_skips_entries_without_name(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client_cls.parse_next_link.return_value = None
        mock_client.get.return_value = {
            "dataStores": [None, "", {"no_name_key": "value"}, "Worker"]
        }

        candidates = discover_module._list_discovery_candidates(mock_client, {})
        self.assertEqual(candidates, ["Worker"])


class TestDiscoveryRunnerLogProgress(unittest.TestCase):
    @mock.patch("tap_oracle_fusion.discover.OracleClient")
    def test_log_progress_logs_first_item(self, mock_client_cls):
        mock_client_cls.return_value  # ignore
        runner = discover_module.BICCDiscoveryRunner({"base_url": "https://example"})
        runner._total_count = 5

        with mock.patch.object(discover_module.LOGGER, "info") as mock_log:
            runner._log_progress("Worker")

        # Should log for first item
        mock_log.assert_called()

    @mock.patch("tap_oracle_fusion.discover.OracleClient")
    def test_log_skipped_datastores_when_empty(self, mock_client_cls):
        mock_client_cls.return_value
        runner = discover_module.BICCDiscoveryRunner({"base_url": "https://example"})
        # Should not raise even when empty
        runner._log_skipped_datastores()

    @mock.patch("tap_oracle_fusion.discover.OracleClient")
    def test_log_skipped_datastores_warns(self, mock_client_cls):
        mock_client_cls.return_value
        runner = discover_module.BICCDiscoveryRunner({"base_url": "https://example"})
        runner._skipped_datastores = [("Worker", "reason"), ("Dept", "reason")]

        with mock.patch.object(discover_module.LOGGER, "warning") as mock_warn:
            runner._log_skipped_datastores()

        mock_warn.assert_called_once()


class TestGetStreamResourceMap(unittest.TestCase):
    @mock.patch("tap_oracle_fusion.discover.OracleClient")
    def test_builds_stream_to_path_map(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client_cls.parse_next_link.return_value = None
        mock_client.get.return_value = {"dataStores": ["FscmTopModelAM.Worker"]}

        result = discover_module.get_stream_resource_map({"base_url": "https://example"})
        self.assertIn("fscmtopmodelam_worker", result)
        self.assertIn("biacm/rest/meta/datastores", result["fscmtopmodelam_worker"])

    @mock.patch("tap_oracle_fusion.discover.OracleClient")
    def test_deduplicates_streams(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client_cls.parse_next_link.return_value = None
        mock_client.get.return_value = {
            "dataStores": ["FscmTopModelAM.Worker", "fscmtopmodelam.worker"]
        }

        result = discover_module.get_stream_resource_map({"base_url": "https://example"})
        # Both map to same normalized name → only one entry
        self.assertEqual(len(result), 1)

    @mock.patch("tap_oracle_fusion.discover.OracleClient")
    def test_continue_on_duplicate_normalized_names(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client_cls.parse_next_link.return_value = None
        # Hyphen and underscore both normalize to '_', so both yield the same
        # stream name but have different lowercased forms (pass through candidate
        # dedup) — the second hits the `continue` in get_stream_resource_map.
        mock_client.get.return_value = {
            "dataStores": ["FscmTopModelAM-Worker", "FscmTopModelAM_Worker"]
        }
        result = discover_module.get_stream_resource_map({"base_url": "https://example"})
        self.assertEqual(len(result), 1)


class TestExtractDatastoreEntriesEmpty(unittest.TestCase):
    def test_returns_empty_for_unrecognized_keys(self):
        result = discover_module._extract_datastore_entries({"unknown_key": ["a", "b"]})
        self.assertEqual(result, [])


class TestGetDiscoveryLimit(unittest.TestCase):
    def test_returns_none_by_default(self):
        self.assertIsNone(discover_module._get_discovery_limit({}))

    def test_returns_parsed_positive_int(self):
        self.assertEqual(discover_module._get_discovery_limit({"discovery_limit": 50}), 50)

    def test_invalid_value_type_triggers_continue(self):
        # int([1, 2]) raises TypeError -> except branch -> returns None
        result = discover_module._get_discovery_limit({"discovery_limit": [1, 2]})
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
