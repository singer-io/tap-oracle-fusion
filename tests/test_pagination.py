"""Pagination test for tap-oracle-fusion.

BICC streams extract data as CSV files via the Oracle UCM content server.
The Oracle ESS job handles all filtering and pagination on the server side;
the tap streams rows directly from the downloaded file without a client-side
offset/limit loop.  Consequently the standard ``PaginationTest`` mixin
(which requires ``API_LIMIT`` in metadata and asserts record count >
page size) does not apply to BICC streams.
"""

import unittest

from base import OracleFusionBaseTest
from tap_tester import connections, runner


class OracleFusionPaginationTest(OracleFusionBaseTest):
    """Verify extract completeness and record uniqueness for BICC streams.

    BICC extracts retrieve all data in a single bulk file download.  This
    test confirms the file is parsed correctly with no dropped or duplicate
    records.
    """

    @staticmethod
    def name():
        return "tap_tester_oracle_fusion_pagination_test"

    def streams_to_test(self):
        return self.expected_stream_names()

    @staticmethod
    def streams_to_selected_fields():
        """Select all available fields for all streams under test."""
        return {}

    # -------------------------------------------------------------------------
    # Class-level cache — shared across test_ methods.
    # -------------------------------------------------------------------------
    _synced_records = None
    _record_count_by_stream = None
    _schemas_by_stream = None

    def setUp(self):  # pylint: disable=invalid-name
        super().setUp(logging="Run setup for OracleFusionPaginationTest")

        if all(
            [
                OracleFusionPaginationTest._synced_records,
                OracleFusionPaginationTest._record_count_by_stream,
            ]
        ):
            return

        conn_id = connections.ensure_connection(self)
        found_catalogs = self.run_and_verify_check_mode(conn_id)

        test_catalogs = [
            c
            for c in found_catalogs
            if c.get("stream_name") in self.streams_to_test()
        ]
        self.perform_and_verify_table_and_field_selection(conn_id, test_catalogs)

        OracleFusionPaginationTest._record_count_by_stream = self.run_and_verify_sync_mode(conn_id)
        OracleFusionPaginationTest._synced_records = runner.get_records_from_target_output()
        OracleFusionPaginationTest._schemas_by_stream = {
            stream: data.get("schema", {})
            for stream, data in OracleFusionPaginationTest._synced_records.items()
        }

    # -------------------------------------------------------------------------
    # Tests
    # -------------------------------------------------------------------------

    def test_all_streams_return_records(self):
        """Every selected stream should return at least one record.

        BICC extracts that return zero records typically indicate a
        configuration problem (e.g. the Oracle job could not find data for
        the given ``initial_extract_date``).
        """
        for stream in self.streams_to_test():
            with self.subTest(stream=stream):
                count = self._record_count_by_stream.get(stream, 0)
                self.assertGreater(
                    count,
                    0,
                    msg=(
                        f"Stream '{stream}' returned 0 records. "
                        "Check that the Oracle environment has data and that "
                        "'initial_extract_date' is set far enough in the past."
                    ),
                )

    def test_no_duplicate_records_for_streams_with_primary_keys(self):
        """For streams that declare primary keys, verify that every PK tuple
        is unique in the extracted data.

        Duplicate records can appear if the UCM file was downloaded twice or
        if the CSV parsing logic incorrectly reprocesses rows.
        """
        streams_with_pks = {
            s for s in self.streams_to_test() if self.expected_primary_keys(s)
        }

        for stream in streams_with_pks:
            with self.subTest(stream=stream):
                expected_pks = self.expected_primary_keys(stream)
                messages = self._synced_records.get(stream, {}).get("messages", [])
                upsert_records = [m["data"] for m in messages if m.get("action") == "upsert"]

                pk_tuples = [
                    tuple(record.get(pk) for pk in sorted(expected_pks))
                    for record in upsert_records
                ]
                unique_pk_tuples = set(pk_tuples)

                self.assertEqual(
                    len(pk_tuples),
                    len(unique_pk_tuples),
                    msg=(
                        f"Stream '{stream}' has {len(pk_tuples) - len(unique_pk_tuples)} "
                        f"duplicate record(s) by primary key {sorted(expected_pks)}."
                    ),
                )

    @unittest.skip(
        "BICC streams do not use client-side offset/limit pagination.  "
        "The Oracle ESS job controls all data filtering.  There is no page "
        "limit to assert against for BICC extracts."
    )
    def test_record_count_greater_than_page_limit(self):
        """Not applicable to BICC streams.  See module docstring for details."""

    def test_schema_fields_present_in_records(self):
        """Verify that every field declared in the Singer SCHEMA message for a
        stream appears in at least one emitted record.

        For BICC streams the schema is generated dynamically from the Oracle
        BICC attribute metadata.  Missing fields in records suggest the CSV
        column mapping has a gap.

        Note: This test checks field *presence* across the union of all
        records.  A field that legitimately has ``null`` values in every row
        may still appear as a key in the record dict.
        """
        for stream in self.streams_to_test():
            with self.subTest(stream=stream):
                schema = self._schemas_by_stream.get(stream, {})
                declared_fields = set(schema.get("properties", {}).keys())
                if not declared_fields:
                    continue  # Dynamic schema with no declared properties — skip.

                messages = self._synced_records.get(stream, {}).get("messages", [])
                upsert_records = [m["data"] for m in messages if m.get("action") == "upsert"]

                # Collect all fields that appear across all records.
                fields_in_records: set = set()
                for record in upsert_records:
                    fields_in_records.update(record.keys())

                missing_from_records = declared_fields - fields_in_records
                self.assertSetEqual(
                    set(),
                    missing_from_records,
                    msg=(
                        f"Stream '{stream}': the following schema fields were never "
                        f"present in any record: {missing_from_records}"
                    ),
                )
