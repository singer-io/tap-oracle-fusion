"""Extended tests for tap_oracle_fusion.sync module — helpers and full sync paths."""
import importlib
import unittest
from unittest import mock

from singer import metadata
from singer.catalog import CatalogEntry, Schema

from tap_oracle_fusion.schema import ENTITY_SET_METADATA_KEY, DATASTORE_KEY_METADATA_KEY

sync_module = importlib.import_module("tap_oracle_fusion.sync")


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------

def _make_entry(
    stream_name: str,
    oracle_path: str = "",
    datastore_key: str = "",
    key_properties: list = None,
    schema_dict: dict = None,
    replication_key: str = "",
) -> CatalogEntry:
    mdata = metadata.new()
    if oracle_path:
        mdata = metadata.write(mdata, (), ENTITY_SET_METADATA_KEY, oracle_path)
    if datastore_key:
        mdata = metadata.write(mdata, (), DATASTORE_KEY_METADATA_KEY, datastore_key)
    if replication_key:
        mdata = metadata.write(mdata, (), "valid-replication-keys", [replication_key])

    if schema_dict is None:
        schema_dict = {"type": "object", "properties": {"Id": {"type": ["null", "string"]}}}

    return CatalogEntry(
        stream=stream_name,
        tap_stream_id=stream_name,
        key_properties=key_properties or [],
        schema=Schema.from_dict(schema_dict),
        metadata=metadata.to_list(mdata),
    )


def _make_catalog(*entries):
    cat = mock.Mock()
    cat.get_selected_streams.return_value = [
        mock.Mock(tap_stream_id=e.tap_stream_id) for e in entries
    ]
    lookup = {e.tap_stream_id: e for e in entries}
    cat.get_stream.side_effect = lambda sid: lookup[sid]
    return cat


# ---------------------------------------------------------------------------
# Helper function unit tests
# ---------------------------------------------------------------------------

class TestParseTimestamp(unittest.TestCase):
    def test_valid_iso_with_z(self):
        result = sync_module._parse_timestamp("2023-01-15T10:30:00Z")
        self.assertIsNotNone(result)

    def test_valid_iso_with_offset(self):
        result = sync_module._parse_timestamp("2023-01-15T10:30:00+00:00")
        self.assertIsNotNone(result)

    def test_invalid_string_returns_none(self):
        self.assertIsNone(sync_module._parse_timestamp("not-a-date"))

    def test_none_returns_none(self):
        self.assertIsNone(sync_module._parse_timestamp(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(sync_module._parse_timestamp(""))

    def test_non_string_returns_none(self):
        self.assertIsNone(sync_module._parse_timestamp(12345))


class TestSanitizeFloatValues(unittest.TestCase):
    def test_finite_float_unchanged(self):
        self.assertEqual(sync_module._sanitize_float_values(3.14), 3.14)

    def test_nan_becomes_none(self):
        self.assertIsNone(sync_module._sanitize_float_values(float("nan")))

    def test_positive_inf_becomes_none(self):
        self.assertIsNone(sync_module._sanitize_float_values(float("inf")))

    def test_negative_inf_becomes_none(self):
        self.assertIsNone(sync_module._sanitize_float_values(float("-inf")))

    def test_non_float_scalar_unchanged(self):
        self.assertEqual(sync_module._sanitize_float_values("hello"), "hello")
        self.assertEqual(sync_module._sanitize_float_values(42), 42)
        self.assertIsNone(sync_module._sanitize_float_values(None))
        self.assertTrue(sync_module._sanitize_float_values(True))

    def test_dict_sanitizes_values(self):
        record = {"a": 1.5, "b": float("nan"), "c": float("inf"), "d": "ok"}
        result = sync_module._sanitize_float_values(record)
        self.assertEqual(result, {"a": 1.5, "b": None, "c": None, "d": "ok"})

    def test_dict_keys_preserved(self):
        record = {"x": float("-inf")}
        result = sync_module._sanitize_float_values(record)
        self.assertIn("x", result)
        self.assertIsNone(result["x"])

    def test_list_sanitizes_elements(self):
        lst = [1.0, float("nan"), float("inf"), "text", None]
        result = sync_module._sanitize_float_values(lst)
        self.assertEqual(result, [1.0, None, None, "text", None])

    def test_nested_dict_sanitizes_deeply(self):
        record = {"outer": {"inner": float("nan"), "val": 2.0}}
        result = sync_module._sanitize_float_values(record)
        self.assertIsNone(result["outer"]["inner"])
        self.assertEqual(result["outer"]["val"], 2.0)

    def test_nested_list_in_dict(self):
        record = {"items": [float("inf"), 1, float("nan")]}
        result = sync_module._sanitize_float_values(record)
        self.assertEqual(result["items"], [None, 1, None])

    def test_empty_dict_returns_empty_dict(self):
        self.assertEqual(sync_module._sanitize_float_values({}), {})

    def test_empty_list_returns_empty_list(self):
        self.assertEqual(sync_module._sanitize_float_values([]), [])

    def test_result_is_json_serializable(self):
        import json
        record = {"a": float("nan"), "b": float("inf"), "c": 1.5, "d": [float("-inf"), 0]}
        sanitized = sync_module._sanitize_float_values(record)
        # should not raise
        json.dumps(sanitized)


class TestStateIsValid(unittest.TestCase):
    def test_empty_dict_is_valid(self):
        self.assertTrue(sync_module._state_is_valid({}))

    def test_dict_with_bookmarks_dict_is_valid(self):
        self.assertTrue(sync_module._state_is_valid({"bookmarks": {}}))

    def test_dict_with_bookmarks_non_dict_is_invalid(self):
        self.assertFalse(sync_module._state_is_valid({"bookmarks": "bad"}))

    def test_non_dict_is_invalid(self):
        self.assertFalse(sync_module._state_is_valid(None))
        self.assertFalse(sync_module._state_is_valid([]))


class TestGetReplicationKey(unittest.TestCase):
    def test_returns_first_replication_key(self):
        entry = _make_entry("s", replication_key="LastUpdateDate")
        self.assertEqual(sync_module._get_replication_key(entry), "LastUpdateDate")

    def test_returns_none_when_no_keys(self):
        entry = _make_entry("s")
        self.assertIsNone(sync_module._get_replication_key(entry))


class TestGetOraclePath(unittest.TestCase):
    def test_returns_path_from_metadata(self):
        entry = _make_entry("s", oracle_path="some/path/to/resource")
        self.assertEqual(sync_module._get_oracle_path(entry), "some/path/to/resource")

    def test_returns_empty_when_missing(self):
        entry = _make_entry("s")
        self.assertEqual(sync_module._get_oracle_path(entry), "")


class TestDatastoreFromPath(unittest.TestCase):
    def test_extracts_datastore_from_path(self):
        result = sync_module._datastore_from_path(
            "biacm/rest/meta/datastores/FscmTopModelAM.Worker"
        )
        self.assertEqual(result, "FscmTopModelAM.Worker")

    def test_returns_none_for_empty_path(self):
        self.assertIsNone(sync_module._datastore_from_path(""))

    def test_returns_none_when_prefix_missing(self):
        self.assertIsNone(sync_module._datastore_from_path("some/other/path"))

    def test_returns_none_when_nothing_after_prefix(self):
        self.assertIsNone(sync_module._datastore_from_path("biacm/rest/meta/datastores/"))


class TestGetDatastoreName(unittest.TestCase):
    def test_uses_metadata_datastore_key(self):
        entry = _make_entry("s", datastore_key="FscmTopModelAM.Worker")
        result = sync_module._get_datastore_name(entry, "biacm/rest/meta/datastores/x")
        self.assertEqual(result, "FscmTopModelAM.Worker")

    def test_falls_back_to_path_parsing(self):
        entry = _make_entry("s")
        result = sync_module._get_datastore_name(
            entry, "biacm/rest/meta/datastores/FscmTopModelAM.Department"
        )
        self.assertEqual(result, "FscmTopModelAM.Department")


class TestSchemaPropertyLookup(unittest.TestCase):
    def test_builds_lowercase_map(self):
        schema = {"properties": {"WorkerId": {}, "Name": {}}}
        result = sync_module._schema_property_lookup(schema)
        self.assertEqual(result["workerid"], "WorkerId")
        self.assertEqual(result["name"], "Name")

    def test_returns_empty_for_no_properties(self):
        self.assertEqual(sync_module._schema_property_lookup({}), {})

    def test_returns_empty_for_non_mapping_properties(self):
        self.assertEqual(sync_module._schema_property_lookup({"properties": "bad"}), {})


class TestNormalizeRecordKeysForSchema(unittest.TestCase):
    def test_normalizes_case(self):
        record = {"workerid": "123", "name": "Alice"}
        lookup = {"workerid": "WorkerId", "name": "Name"}
        result = sync_module._normalize_record_keys_for_schema(record, lookup)
        self.assertIn("WorkerId", result)
        self.assertIn("Name", result)

    def test_passes_through_when_no_lookup(self):
        record = {"workerid": "123"}
        result = sync_module._normalize_record_keys_for_schema(record, {})
        self.assertEqual(result, {"workerid": "123"})

    def test_passes_through_non_string_keys(self):
        record = {1: "value", "name": "Alice"}
        lookup = {"name": "Name"}
        result = sync_module._normalize_record_keys_for_schema(record, lookup)
        self.assertEqual(result[1], "value")
        self.assertEqual(result["Name"], "Alice")


class TestIsDatetimeProperty(unittest.TestCase):
    def test_true_for_date_time_format(self):
        self.assertTrue(sync_module._is_datetime_property({"format": "date-time"}))

    def test_false_for_missing_format(self):
        self.assertFalse(sync_module._is_datetime_property({"type": "string"}))

    def test_false_for_non_mapping(self):
        self.assertFalse(sync_module._is_datetime_property("string"))


class TestDatetimeSchemaFields(unittest.TestCase):
    def test_returns_datetime_field_names(self):
        schema = {
            "properties": {
                "LastUpdateDate": {"format": "date-time"},
                "WorkerId": {"type": ["null", "string"]},
            }
        }
        result = sync_module._datetime_schema_fields(schema)
        self.assertIn("LastUpdateDate", result)
        self.assertNotIn("WorkerId", result)

    def test_returns_empty_for_no_properties(self):
        self.assertEqual(sync_module._datetime_schema_fields({}), set())

    def test_returns_empty_for_non_mapping_properties(self):
        self.assertEqual(sync_module._datetime_schema_fields({"properties": None}), set())


class TestIsValidDatetimeValue(unittest.TestCase):
    def test_none_is_valid(self):
        self.assertTrue(sync_module._is_valid_datetime_value(None))

    def test_empty_string_is_valid(self):
        self.assertTrue(sync_module._is_valid_datetime_value(""))
        self.assertTrue(sync_module._is_valid_datetime_value("   "))

    def test_valid_iso_string(self):
        self.assertTrue(sync_module._is_valid_datetime_value("2023-01-15T10:30:00Z"))

    def test_invalid_string(self):
        self.assertFalse(sync_module._is_valid_datetime_value("not-a-date"))

    def test_non_string_non_none(self):
        self.assertFalse(sync_module._is_valid_datetime_value(12345))


class TestSanitizeRecordDatetimes(unittest.TestCase):
    def test_no_datetime_fields_returns_record_unchanged(self):
        record = {"Id": "1", "Name": "Alice"}
        result = sync_module._sanitize_record_datetimes_for_schema(
            record, set(), "stream", set()
        )
        self.assertEqual(result, {"Id": "1", "Name": "Alice"})

    def test_valid_datetime_unchanged(self):
        record = {"LastUpdateDate": "2023-01-15T10:30:00Z"}
        result = sync_module._sanitize_record_datetimes_for_schema(
            record, {"LastUpdateDate"}, "stream", set()
        )
        self.assertEqual(result["LastUpdateDate"], "2023-01-15T10:30:00Z")

    def test_invalid_datetime_replaced_with_none(self):
        record = {"LastUpdateDate": "bad-date-value"}
        warned = set()
        result = sync_module._sanitize_record_datetimes_for_schema(
            record, {"LastUpdateDate"}, "stream", warned
        )
        self.assertIsNone(result["LastUpdateDate"])
        self.assertEqual(len(warned), 1)

    def test_warning_only_logged_once_per_unique_value(self):
        warned = set()
        for _ in range(3):
            sync_module._sanitize_record_datetimes_for_schema(
                {"dt": "bad"}, {"dt"}, "stream", warned
            )
        self.assertEqual(len(warned), 1)

    def test_field_not_in_record_skipped(self):
        record = {"other_field": "value"}
        result = sync_module._sanitize_record_datetimes_for_schema(
            record, {"LastUpdateDate"}, "stream", set()
        )
        self.assertEqual(result, {"other_field": "value"})


class TestIsUnsupportedDatastoreError(unittest.TestCase):
    def test_jbo_and_fk_constraint_is_unsupported(self):
        err = Exception("JBO-26048 error C_JOB_DATA_STORE_REL_C_DA_FK1 constraint")
        self.assertTrue(sync_module._is_unsupported_datastore_create_job_error(err))

    def test_other_error_is_not_unsupported(self):
        err = Exception("Some other error")
        self.assertFalse(sync_module._is_unsupported_datastore_create_job_error(err))


class TestBookmarkHelpers(unittest.TestCase):
    def test_bookmark_value_returns_default(self):
        result = sync_module._bookmark_value({}, "stream", "LastUpdateDate", "2020-01-01")
        self.assertEqual(result, "2020-01-01")

    def test_bookmark_value_returns_stored(self):
        state = {"bookmarks": {"stream": {"LastUpdateDate": "2023-06-01"}}}
        result = sync_module._bookmark_value(state, "stream", "LastUpdateDate", "2020-01-01")
        self.assertEqual(result, "2023-06-01")

    def test_write_bookmark(self):
        state = {}
        new_state = sync_module._write_bookmark(state, "stream", "LastUpdateDate", "2023-06-15")
        stored = new_state.get("bookmarks", {}).get("stream", {}).get("LastUpdateDate")
        self.assertEqual(stored, "2023-06-15")

    def test_build_incremental_query(self):
        result = sync_module._build_incremental_query("LastUpdateDate", "2023-01-01T00:00:00Z")
        self.assertIn("LastUpdateDate", result["q"])
        self.assertIn("2023-01-01T00:00:00Z", result["q"])


class TestMetadataPathIsBicc(unittest.TestCase):
    def test_bicc_path(self):
        self.assertTrue(sync_module._metadata_path_is_bicc("biacm/rest/meta/datastores/X"))

    def test_non_bicc_path(self):
        self.assertFalse(sync_module._metadata_path_is_bicc("hcmRestApi/resources/Workers"))


# ---------------------------------------------------------------------------
# Full sync() path tests
# ---------------------------------------------------------------------------

class TestSyncInvalidState(unittest.TestCase):
    @mock.patch("tap_oracle_fusion.sync.OracleClient")
    @mock.patch("tap_oracle_fusion.sync.BICCExtractClient")
    def test_raises_on_invalid_state(self, _bicc, _client):
        with self.assertRaises(RuntimeError) as ctx:
            sync_module.sync(
                {"base_url": "https://example"},
                mock.Mock(get_selected_streams=lambda s: []),
                {"bookmarks": "not-a-dict"},
            )
        self.assertIn("Invalid state", str(ctx.exception))


class TestSyncRestStream(unittest.TestCase):
    @mock.patch("tap_oracle_fusion.sync.singer.write_state")
    @mock.patch("tap_oracle_fusion.sync.singer.write_record")
    @mock.patch("tap_oracle_fusion.sync.singer.write_schema")
    @mock.patch("tap_oracle_fusion.sync.BICCExtractClient")
    @mock.patch("tap_oracle_fusion.sync.OracleClient")
    def test_rest_stream_emits_records(
        self, mock_client_cls, mock_bicc_cls, _ws, mock_wr, _wstate
    ):
        mock_client = mock_client_cls.return_value
        mock_client.get_records.return_value = iter([
            {"Id": "1", "Name": "Alice"},
            {"Id": "2", "Name": "Bob"},
        ])

        entry = _make_entry(
            "workers",
            oracle_path="hcmRestApi/resources/11.13.18.05/workers",
        )
        catalog = _make_catalog(entry)
        sync_module.sync({"base_url": "https://example"}, catalog, {})

        self.assertEqual(mock_wr.call_count, 2)

    @mock.patch("tap_oracle_fusion.sync.singer.write_state")
    @mock.patch("tap_oracle_fusion.sync.singer.write_record")
    @mock.patch("tap_oracle_fusion.sync.singer.write_schema")
    @mock.patch("tap_oracle_fusion.sync.BICCExtractClient")
    @mock.patch("tap_oracle_fusion.sync.OracleClient")
    def test_rest_stream_with_replication_key_updates_bookmark(
        self, mock_client_cls, mock_bicc_cls, _ws, _wr, mock_write_state
    ):
        mock_client = mock_client_cls.return_value
        mock_client.get_records.return_value = iter([
            {"Id": "1", "LastUpdateDate": "2023-06-15T00:00:00Z"},
        ])

        schema_dict = {
            "type": "object",
            "properties": {
                "Id": {"type": ["null", "string"]},
                "LastUpdateDate": {"type": ["null", "string"], "format": "date-time"},
            },
        }
        entry = _make_entry(
            "workers",
            oracle_path="hcmRestApi/resources/11.13.18.05/workers",
            replication_key="LastUpdateDate",
            schema_dict=schema_dict,
        )
        catalog = _make_catalog(entry)
        config = {
            "base_url": "https://example",
            "start_date": "2020-01-01T00:00:00Z",
        }
        sync_module.sync(config, catalog, {})
        # State should have been written at least once
        self.assertTrue(mock_write_state.called)


class TestSyncBiccStream(unittest.TestCase):
    @mock.patch("tap_oracle_fusion.sync.singer.write_state")
    @mock.patch("tap_oracle_fusion.sync.singer.write_record")
    @mock.patch("tap_oracle_fusion.sync.singer.write_schema")
    @mock.patch("tap_oracle_fusion.sync.BICCExtractClient")
    @mock.patch("tap_oracle_fusion.sync.OracleClient")
    def test_bicc_stream_emits_records(
        self, _client_cls, mock_bicc_cls, _ws, mock_wr, _wstate
    ):
        mock_bicc = mock_bicc_cls.return_value
        mock_bicc.create_bicc_job.return_value = "job-1"
        mock_bicc.run_extract_to_rows.return_value = (
            iter([{"Id": "1", "Name": "Alice"}, {"Id": "2", "Name": "Bob"}]),
            {"state": "SUCCEEDED"},
        )

        entry = _make_entry(
            "worker",
            oracle_path="biacm/rest/meta/datastores/FscmTopModelAM.Worker",
            datastore_key="FscmTopModelAM.Worker",
        )
        catalog = _make_catalog(entry)
        sync_module.sync({"base_url": "https://example"}, catalog, {})
        self.assertEqual(mock_wr.call_count, 2)

    @mock.patch("tap_oracle_fusion.sync.singer.write_state")
    @mock.patch("tap_oracle_fusion.sync.singer.write_record")
    @mock.patch("tap_oracle_fusion.sync.singer.write_schema")
    @mock.patch("tap_oracle_fusion.sync.BICCExtractClient")
    @mock.patch("tap_oracle_fusion.sync.OracleClient")
    def test_bicc_stream_pk_deduplication(
        self, _client_cls, mock_bicc_cls, _ws, mock_wr, _wstate
    ):
        mock_bicc = mock_bicc_cls.return_value
        mock_bicc.create_bicc_job.return_value = "job-1"
        # Two records with the same PK → only one should be emitted
        mock_bicc.run_extract_to_rows.return_value = (
            iter([
                {"Id": "1", "Name": "Alice"},
                {"Id": "1", "Name": "Alice"},
            ]),
            {"state": "SUCCEEDED"},
        )

        entry = _make_entry(
            "worker",
            oracle_path="biacm/rest/meta/datastores/FscmTopModelAM.Worker",
            datastore_key="FscmTopModelAM.Worker",
            key_properties=["Id"],
        )
        catalog = _make_catalog(entry)
        sync_module.sync({"base_url": "https://example"}, catalog, {})
        self.assertEqual(mock_wr.call_count, 1)

    @mock.patch("tap_oracle_fusion.sync.singer.write_state")
    @mock.patch("tap_oracle_fusion.sync.singer.write_record")
    @mock.patch("tap_oracle_fusion.sync.singer.write_schema")
    @mock.patch("tap_oracle_fusion.sync.BICCExtractClient")
    @mock.patch("tap_oracle_fusion.sync.OracleClient")
    def test_bicc_stream_pk_deduplication_keeps_first_on_value_change(
        self, _client_cls, mock_bicc_cls, _ws, mock_wr, _wstate
    ):
        """Same PK but DIFFERENT values: dedup still keeps only the first row.

        This documents a known limitation: if BICC legitimately emits multiple
        change events for the same PK in a single extract (e.g. the row was
        updated twice within the extract window), only the first event is
        emitted and the later update is silently dropped.  If Oracle BICC
        guarantees at-most-one row per PK per extract, this behavior is safe;
        if it does not, downstream data may be stale.
        """
        mock_bicc = mock_bicc_cls.return_value
        mock_bicc.create_bicc_job.return_value = "job-1"
        mock_bicc.run_extract_to_rows.return_value = (
            iter([
                {"Id": "1", "Name": "Alice"},   # first event
                {"Id": "1", "Name": "Alice_v2"}, # later update — same PK, different value
            ]),
            {"state": "SUCCEEDED"},
        )

        schema_dict = {
            "type": "object",
            "properties": {
                "Id": {"type": ["null", "string"]},
                "Name": {"type": ["null", "string"]},
            },
        }
        entry = _make_entry(
            "worker",
            oracle_path="biacm/rest/meta/datastores/FscmTopModelAM.Worker",
            datastore_key="FscmTopModelAM.Worker",
            key_properties=["Id"],
            schema_dict=schema_dict,
        )
        catalog = _make_catalog(entry)
        sync_module.sync({"base_url": "https://example"}, catalog, {})
        # Only the first event survives; the later update is dropped.
        self.assertEqual(mock_wr.call_count, 1)
        emitted_record = mock_wr.call_args[0][1]
        self.assertEqual(emitted_record.get("Name"), "Alice")


    @mock.patch("tap_oracle_fusion.sync.singer.write_state")
    @mock.patch("tap_oracle_fusion.sync.singer.write_record")
    @mock.patch("tap_oracle_fusion.sync.singer.write_schema")
    @mock.patch("tap_oracle_fusion.sync.BICCExtractClient")
    @mock.patch("tap_oracle_fusion.sync.OracleClient")
    def test_bicc_unsupported_datastore_error_skips_stream(
        self, _client_cls, mock_bicc_cls, _ws, mock_wr, _wstate
    ):
        from tap_oracle_fusion.bicc_extract import ExtractError

        mock_bicc = mock_bicc_cls.return_value
        mock_bicc.create_bicc_job.side_effect = ExtractError(
            "JBO-26048 some C_JOB_DATA_STORE_REL_C_DA_FK1 constraint error"
        )

        entry = _make_entry(
            "worker",
            oracle_path="biacm/rest/meta/datastores/FscmTopModelAM.Worker",
            datastore_key="FscmTopModelAM.Worker",
        )
        catalog = _make_catalog(entry)
        # Should not raise — stream is silently skipped
        sync_module.sync({"base_url": "https://example"}, catalog, {})
        mock_wr.assert_not_called()

    @mock.patch("tap_oracle_fusion.sync.singer.write_state")
    @mock.patch("tap_oracle_fusion.sync.singer.write_record")
    @mock.patch("tap_oracle_fusion.sync.singer.write_schema")
    @mock.patch("tap_oracle_fusion.sync.BICCExtractClient")
    @mock.patch("tap_oracle_fusion.sync.OracleClient")
    def test_bicc_ess_extract_error_skips_stream(
        self, _client_cls, mock_bicc_cls, _ws, mock_wr, _wstate
    ):
        from tap_oracle_fusion.bicc_extract import ExtractError

        mock_bicc = mock_bicc_cls.return_value
        mock_bicc.create_bicc_job.side_effect = ExtractError("ESS job failed: unexpected error")

        entry = _make_entry(
            "worker",
            oracle_path="biacm/rest/meta/datastores/FscmTopModelAM.Worker",
            datastore_key="FscmTopModelAM.Worker",
        )
        catalog = _make_catalog(entry)
        sync_module.sync({"base_url": "https://example"}, catalog, {})
        mock_wr.assert_not_called()

    @mock.patch("tap_oracle_fusion.sync.singer.write_state")
    @mock.patch("tap_oracle_fusion.sync.singer.write_record")
    @mock.patch("tap_oracle_fusion.sync.singer.write_schema")
    @mock.patch("tap_oracle_fusion.sync.BICCExtractClient")
    @mock.patch("tap_oracle_fusion.sync.OracleClient")
    def test_bicc_stream_raises_when_no_datastore_name(
        self, _client_cls, mock_bicc_cls, _ws, _wr, _wstate
    ):
        entry = _make_entry(
            "worker",
            oracle_path="biacm/rest/meta/datastores/",  # empty after prefix
        )
        catalog = _make_catalog(entry)
        with self.assertRaises(RuntimeError) as ctx:
            sync_module.sync({"base_url": "https://example"}, catalog, {})
        self.assertIn("datastore name", str(ctx.exception))

    @mock.patch("tap_oracle_fusion.sync.singer.write_state")
    @mock.patch("tap_oracle_fusion.sync.singer.write_record")
    @mock.patch("tap_oracle_fusion.sync.singer.write_schema")
    @mock.patch("tap_oracle_fusion.sync.BICCExtractClient")
    @mock.patch("tap_oracle_fusion.sync.OracleClient")
    def test_bicc_stream_datetime_sanitization(
        self, _client_cls, mock_bicc_cls, _ws, mock_wr, _wstate
    ):
        mock_bicc = mock_bicc_cls.return_value
        mock_bicc.create_bicc_job.return_value = "job-1"
        mock_bicc.run_extract_to_rows.return_value = (
            iter([{"Id": "1", "LastUpdateDate": "not-a-valid-date"}]),
            {"state": "SUCCEEDED"},
        )

        schema_dict = {
            "type": "object",
            "properties": {
                "Id": {"type": ["null", "string"]},
                "LastUpdateDate": {"type": ["null", "string"], "format": "date-time"},
            },
        }
        entry = _make_entry(
            "worker",
            oracle_path="biacm/rest/meta/datastores/FscmTopModelAM.Worker",
            datastore_key="FscmTopModelAM.Worker",
            schema_dict=schema_dict,
        )
        catalog = _make_catalog(entry)
        sync_module.sync({"base_url": "https://example"}, catalog, {})
        # Record should have been written with None for the invalid date
        self.assertEqual(mock_wr.call_count, 1)
        written_record = mock_wr.call_args[0][1]
        self.assertIsNone(written_record.get("LastUpdateDate"))


class TestUpdateCurrentlySyncing(unittest.TestCase):
    @mock.patch("tap_oracle_fusion.sync.singer.write_state")
    def test_sets_currently_syncing(self, mock_write_state):
        state = {}
        sync_module.update_currently_syncing(state, "my_stream")
        mock_write_state.assert_called_once()

    @mock.patch("tap_oracle_fusion.sync.singer.write_state")
    def test_clears_currently_syncing_when_none(self, _write_state):
        state = {"currently_syncing": "my_stream"}
        sync_module.update_currently_syncing(state, None)
        self.assertNotIn("currently_syncing", state)

    @mock.patch("tap_oracle_fusion.sync.singer.write_state")
    def test_sets_when_stream_provided_even_if_no_current(self, _write_state):
        state = {}
        sync_module.update_currently_syncing(state, "new_stream")
        self.assertEqual(state.get("currently_syncing"), "new_stream")


class TestSyncReplicationKeyBookmarking(unittest.TestCase):
    @mock.patch("tap_oracle_fusion.sync.singer.write_state")
    @mock.patch("tap_oracle_fusion.sync.singer.write_record")
    @mock.patch("tap_oracle_fusion.sync.singer.write_schema")
    @mock.patch("tap_oracle_fusion.sync.BICCExtractClient")
    @mock.patch("tap_oracle_fusion.sync.OracleClient")
    def test_incremental_bookmark_advanced_correctly(
        self, mock_client_cls, mock_bicc_cls, _ws, _wr, mock_write_state
    ):
        mock_client = mock_client_cls.return_value
        mock_client.get_records.return_value = iter([
            {"Id": "1", "LastUpdateDate": "2023-01-20T00:00:00Z"},
            {"Id": "2", "LastUpdateDate": "2023-06-15T00:00:00Z"},
            {"Id": "3", "LastUpdateDate": "2023-03-01T00:00:00Z"},
        ])

        schema_dict = {
            "type": "object",
            "properties": {
                "Id": {"type": ["null", "string"]},
                "LastUpdateDate": {"type": ["null", "string"], "format": "date-time"},
            },
        }
        entry = _make_entry(
            "workers",
            oracle_path="hcmRestApi/resources/11.13.18.05/workers",
            replication_key="LastUpdateDate",
            schema_dict=schema_dict,
        )
        catalog = _make_catalog(entry)
        config = {"base_url": "https://example", "start_date": "2020-01-01T00:00:00Z"}
        sync_module.sync(config, catalog, {})
        # write_state should have been called and written max bookmark
        state_calls = mock_write_state.call_args_list
        # Find the state that has the bookmark
        written_states = [args[0][0] for args in state_calls if args[0]]
        bookmarked = None
        for st in written_states:
            bm = (st.get("bookmarks") or {}).get("workers", {}).get("LastUpdateDate")
            if bm:
                bookmarked = bm
        self.assertTrue(bookmarked and bookmarked.startswith("2023-06-15T"))

    @mock.patch("tap_oracle_fusion.sync.singer.write_state")
    @mock.patch("tap_oracle_fusion.sync.singer.write_record")
    @mock.patch("tap_oracle_fusion.sync.singer.write_schema")
    @mock.patch("tap_oracle_fusion.sync.BICCExtractClient")
    @mock.patch("tap_oracle_fusion.sync.OracleClient")
    def test_string_comparison_bookmark_fallback(
        self, mock_client_cls, mock_bicc_cls, _ws, _wr, mock_write_state
    ):
        """When timestamps can't be parsed, string comparison is used for bookmarks."""
        mock_client = mock_client_cls.return_value
        mock_client.get_records.return_value = iter([
            {"Id": "1", "RefDate": "2023-09-01"},
            {"Id": "2", "RefDate": "2023-12-31"},
        ])

        schema_dict = {
            "type": "object",
            "properties": {
                "Id": {"type": ["null", "string"]},
                "RefDate": {"type": ["null", "string"]},
            },
        }
        mdata = metadata.new()
        mdata = metadata.write(mdata, (), ENTITY_SET_METADATA_KEY, "hcmRestApi/resources/workers")
        mdata = metadata.write(mdata, (), "valid-replication-keys", ["RefDate"])
        entry = CatalogEntry(
            stream="workers",
            tap_stream_id="workers",
            key_properties=[],
            schema=Schema.from_dict(schema_dict),
            metadata=metadata.to_list(mdata),
        )
        catalog = _make_catalog(entry)
        config = {"base_url": "https://example", "start_date": "2020-01-01"}
        sync_module.sync(config, catalog, {})
        # Should have written state
        self.assertTrue(mock_write_state.called)


class TestSyncRaisesOnUnresolvablePath(unittest.TestCase):
    @mock.patch("tap_oracle_fusion.sync.get_stream_resource_map", return_value={})
    @mock.patch("tap_oracle_fusion.sync.singer.write_schema")
    @mock.patch("tap_oracle_fusion.sync.BICCExtractClient")
    @mock.patch("tap_oracle_fusion.sync.OracleClient")
    def test_raises_runtime_error_when_path_unresolvable(
        self, mock_client_cls, mock_bicc_cls, _ws, mock_resource_map
    ):
        # Stream has no entity-set metadata and discovery map is empty.
        entry = _make_entry("orphan_stream")  # no oracle_path
        catalog = _make_catalog(entry)
        with self.assertRaises(RuntimeError) as ctx:
            sync_module.sync({"base_url": "https://example"}, catalog, {})
        self.assertIn("Could not resolve", str(ctx.exception))


class TestSyncStringReplicationKeyFallback(unittest.TestCase):
    @mock.patch("tap_oracle_fusion.sync.singer.write_state")
    @mock.patch("tap_oracle_fusion.sync.singer.write_record")
    @mock.patch("tap_oracle_fusion.sync.singer.write_schema")
    @mock.patch("tap_oracle_fusion.sync.BICCExtractClient")
    @mock.patch("tap_oracle_fusion.sync.OracleClient")
    def test_non_parseable_replication_value_uses_string_comparison(
        self, mock_client_cls, mock_bicc_cls, _ws, _wr, mock_write_state
    ):
        # Values like 'seq_1' can't be parsed as timestamps → elif string-compare branch.
        mock_client = mock_client_cls.return_value
        mock_client.get_records.return_value = iter([
            {"Id": "1", "SeqId": "seq_1"},
            {"Id": "2", "SeqId": "seq_2"},
        ])
        schema_dict = {
            "type": "object",
            "properties": {
                "Id": {"type": ["null", "string"]},
                "SeqId": {"type": ["null", "string"]},
            },
        }
        entry = _make_entry(
            "workers",
            oracle_path="hcmRestApi/resources/11.13.18.05/workers",
            replication_key="SeqId",
            schema_dict=schema_dict,
        )
        catalog = _make_catalog(entry)
        config = {"base_url": "https://example", "start_date": "seq_0"}
        sync_module.sync(config, catalog, {})
        self.assertTrue(mock_write_state.called)


if __name__ == "__main__":
    unittest.main()
