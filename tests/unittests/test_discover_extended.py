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
        config = {"parent_resource_groups": "FscmTopModelAM, HcmTopModelAM"}
        result = list(discover_module._iter_configured_parents(config))
        self.assertEqual(result, ["FscmTopModelAM", "HcmTopModelAM"])

    def test_list_of_strings(self):
        config = {"parent_resource_groups": ["FscmTopModelAM", "HcmTopModelAM"]}
        result = list(discover_module._iter_configured_parents(config))
        self.assertEqual(result, ["FscmTopModelAM", "HcmTopModelAM"])

    def test_set_of_strings(self):
        config = {"parent_resource_groups": {"FscmTopModelAM"}}
        result = list(discover_module._iter_configured_parents(config))
        self.assertEqual(result, ["FscmTopModelAM"])

    def test_discovery_parents_key_used(self):
        config = {"discovery_parents": ["FscmTopModelAM"]}
        result = list(discover_module._iter_configured_parents(config))
        self.assertEqual(result, ["FscmTopModelAM"])

    def test_other_type_returns_empty(self):
        config = {"parent_resource_groups": 42}
        result = list(discover_module._iter_configured_parents(config))
        self.assertEqual(result, [])

    def test_skips_non_string_items_in_list(self):
        config = {"parent_resource_groups": ["FscmTopModelAM", 123, None]}
        result = list(discover_module._iter_configured_parents(config))
        self.assertEqual(result, ["FscmTopModelAM"])


class TestGetDiscoveryWorkers(unittest.TestCase):
    def test_auto_returns_default(self):
        config = {"discovery_workers": "auto"}
        result = discover_module._get_discovery_workers(config)
        self.assertGreater(result, 0)

    def test_integer_value(self):
        config = {"discovery_workers": 4}
        result = discover_module._get_discovery_workers(config)
        self.assertEqual(result, 4)

    def test_invalid_string_falls_back_to_default(self):
        config = {"discovery_workers": "not-a-number"}
        result = discover_module._get_discovery_workers(config)
        self.assertEqual(result, discover_module.DEFAULT_DISCOVERY_WORKERS)

    def test_zero_falls_back_to_default(self):
        config = {"discovery_workers": 0}
        result = discover_module._get_discovery_workers(config)
        self.assertEqual(result, discover_module.DEFAULT_DISCOVERY_WORKERS)

    def test_capped_at_max(self):
        config = {"discovery_workers": 9999}
        result = discover_module._get_discovery_workers(config)
        self.assertLessEqual(result, discover_module.MAX_DISCOVERY_WORKERS)


class TestGetDiscoveryRetryRounds(unittest.TestCase):
    def test_default_value(self):
        result = discover_module._get_discovery_retry_rounds({})
        self.assertEqual(result, discover_module.DEFAULT_DISCOVERY_RETRY_ROUNDS)

    def test_explicit_value(self):
        result = discover_module._get_discovery_retry_rounds({"discovery_retry_rounds": 5})
        self.assertEqual(result, 5)

    def test_invalid_value_returns_default(self):
        result = discover_module._get_discovery_retry_rounds({"discovery_retry_rounds": "bad"})
        self.assertEqual(result, discover_module.DEFAULT_DISCOVERY_RETRY_ROUNDS)

    def test_negative_returns_zero(self):
        result = discover_module._get_discovery_retry_rounds({"discovery_retry_rounds": -1})
        self.assertEqual(result, 0)


class TestListDatastoresPagination(unittest.TestCase):
    @mock.patch("tap_oracle_fusion.discover.OracleClient")
    def test_follows_has_more_pagination(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client_cls.parse_next_link.return_value = None

        call_count = [0]

        def _fake_get(path, params=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"dataStores": ["A.Store"], "hasMore": True}
            return {"dataStores": ["B.Store"], "hasMore": False}

        mock_client.get.side_effect = _fake_get

        entries = discover_module._list_datastores(mock_client, {"datastore_page_size": 1})
        self.assertEqual(entries, ["A.Store", "B.Store"])
        self.assertEqual(call_count[0], 2)

    @mock.patch("tap_oracle_fusion.discover.OracleClient")
    def test_follows_next_link_pagination(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        call_count = [0]

        def _fake_get(path, params=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"dataStores": ["A.Store"]}
            return {"dataStores": ["B.Store"]}

        mock_client.get.side_effect = _fake_get

        # First call returns next_link, second call returns None
        mock_client_cls.parse_next_link.side_effect = [
            ("biacm/rest/meta/datastores", {"limit": 1, "offset": 1}),
            None,
        ]

        entries = discover_module._list_datastores(mock_client, {})
        self.assertEqual(entries, ["A.Store", "B.Store"])
        self.assertEqual(call_count[0], 2)


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
            "parent_resource_groups": ["FscmTopModelAM"],
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


class TestBuildEntriesRetryable(unittest.TestCase):
    @mock.patch("tap_oracle_fusion.discover.OracleClient")
    def test_sequential_adds_retryable_failure_to_candidates(self, mock_client_cls):
        runner = discover_module.BICCDiscoveryRunner({"base_url": "https://example"})
        runner._total_count = 1
        with mock.patch.object(runner, "_build_entry", return_value=(None, True)):
            entries, retry_candidates = runner._build_entries_sequential(["DS.Worker"])
        self.assertEqual(entries, [])
        self.assertEqual(retry_candidates, ["DS.Worker"])

    @mock.patch("tap_oracle_fusion.discover.OracleClient")
    def test_threaded_adds_retryable_failure_to_candidates(self, mock_client_cls):
        runner = discover_module.BICCDiscoveryRunner({"base_url": "https://example"})
        runner.worker_count = 2
        runner._total_count = 1
        with mock.patch.object(runner, "_build_entry", return_value=(None, True)):
            entries, retry_candidates = runner._build_entries_threaded(["DS.Worker"])
        self.assertEqual(entries, [])
        self.assertEqual(retry_candidates, ["DS.Worker"])


class TestDiscoverRetryRounds(unittest.TestCase):
    @mock.patch("tap_oracle_fusion.discover.OracleClient")
    def test_retry_round_is_logged_and_executed(self, mock_client_cls):
        config = {"base_url": "https://example", "discovery_retry_rounds": 1}
        runner = discover_module.BICCDiscoveryRunner(config)
        with mock.patch.object(runner, "list_candidates", return_value=["DS.Worker"]):
            with mock.patch.object(runner, "_build_entry", return_value=(None, True)):
                with mock.patch.object(discover_module.LOGGER, "info") as mock_log:
                    catalog = runner.discover()
        self.assertEqual(catalog.streams, [])
        retry_calls = [c for c in mock_log.call_args_list if "Retrying" in str(c)]
        self.assertTrue(len(retry_calls) > 0)

    @mock.patch("tap_oracle_fusion.discover.OracleClient")
    def test_persistent_failure_added_to_skipped_after_all_rounds(self, mock_client_cls):
        config = {"base_url": "https://example", "discovery_retry_rounds": 1}
        runner = discover_module.BICCDiscoveryRunner(config)
        with mock.patch.object(runner, "list_candidates", return_value=["DS.Worker"]):
            with mock.patch.object(runner, "_build_entry", return_value=(None, True)):
                catalog = runner.discover()
        self.assertEqual(catalog.streams, [])
        skipped_names = [name for name, _ in runner._skipped_datastores]
        self.assertIn("DS.Worker", skipped_names)


if __name__ == "__main__":
    unittest.main()
