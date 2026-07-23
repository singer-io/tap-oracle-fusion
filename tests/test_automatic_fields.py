"""Automatic-fields test for tap-oracle-fusion.

Verifies that when all non-automatic fields are deselected, only the primary
keys and replication keys (i.e. fields with inclusion=automatic) are emitted
to the target, and that all replicated records have unique primary-key values.

Note: FULL_TABLE streams with no primary keys (e.g. the extensibility custom
objects) are excluded from the uniqueness assertion because there is no key to
compare against.
"""

import unittest

from base import OracleFusionBaseTest
from tap_tester.base_suite_tests.automatic_fields_test import MinimumSelectionTest


class OracleFusionAutomaticFields(MinimumSelectionTest, OracleFusionBaseTest):
    """Test that with no optional fields selected, automatic fields are
    still replicated for every stream."""

    @staticmethod
    def name():
        return "tap_tester_oracle_fusion_automatic_fields_test"

    def streams_to_test(self):
        return self.expected_stream_names()

    def test_records_primary_key_is_unique(self):
        """Only assert PK uniqueness for streams that define primary keys.

        The two FULL_TABLE extensibility streams (task_c, projectstatus_c)
        have no declared primary keys, so uniqueness cannot be verified.
        """
        streams_with_pks = {
            stream
            for stream in self.streams_to_test()
            if self.expected_primary_keys(stream)
        }
        for stream in streams_with_pks:
            with self.subTest(stream=stream):
                expected_primary_keys = self.expected_primary_keys(stream)
                messages = self.synced_messages[stream]["messages"]
                list_of_tupled_pk_values = [
                    tuple(message["data"][pk] for pk in expected_primary_keys)
                    for message in messages
                    if message.get("action") == "upsert"
                ]
                self.assertCountEqual(
                    set(list_of_tupled_pk_values),
                    list_of_tupled_pk_values,
                    logging=f"verify all records for {stream} have unique primary key values",
                )

        streams_without_pks = self.streams_to_test() - streams_with_pks
        for stream in streams_without_pks:
            with self.subTest(stream=stream):
                # No PK uniqueness check possible; just confirm records exist.
                record_count = self.record_count.get(stream, 0)
                self.assertGreater(
                    record_count,
                    0,
                    msg=f"Stream {stream} (no PKs) should still have records",
                )
