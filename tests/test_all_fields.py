from base import Oracle_fusionBaseTest
from tap_tester.base_suite_tests.all_fields_test import AllFieldsTest

KNOWN_MISSING_FIELDS = {

}


class Oracle_fusionAllFields(AllFieldsTest, Oracle_fusionBaseTest):
    """Ensure running the tap with all streams and fields selected results in
    the replication of all fields."""

    @staticmethod
    def name():
        return "tap_tester_oracle_fusion_all_fields_test"

    def streams_to_test(self):
        streams_to_exclude = {}
        return self.expected_stream_names().difference(streams_to_exclude)

