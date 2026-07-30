"""Automatic-fields test for tap-oracle-fusion.

Verifies that when all non-automatic fields are deselected, only the primary
keys and replication keys (i.e. fields with inclusion=automatic) are emitted
to the target.

Note: PK uniqueness is not asserted for BICC streams because BICC produces
CDC-style extracts that can contain multiple rows per primary key (one per
change event within the extract window).
"""

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
        """Skipped: BICC extracts are CDC-style and can contain multiple rows
        per primary key (one per change event within the extract window).
        PK uniqueness is not guaranteed for BICC streams.
        """


