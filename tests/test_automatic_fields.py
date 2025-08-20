"""Test that with no fields selected for a stream automatic fields are still
replicated."""
from base import Oracle_fusionBaseTest
from tap_tester.base_suite_tests.automatic_fields_test import MinimumSelectionTest


class Oracle_fusionAutomaticFields(MinimumSelectionTest, Oracle_fusionBaseTest):
    """Test that with no fields selected for a stream automatic fields are
    still replicated."""

    @staticmethod
    def name():
        return "tap_tester_oracle_fusion_automatic_fields_test"

    def streams_to_test(self):
        streams_to_exclude = {}
        return self.expected_stream_names().difference(streams_to_exclude)

