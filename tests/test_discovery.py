"""Test tap discovery mode and metadata."""
from base import Oracle_fusionBaseTest
from tap_tester.base_suite_tests.discovery_test import DiscoveryTest


class Oracle_fusionDiscoveryTest(DiscoveryTest, Oracle_fusionBaseTest):
    """Test tap discovery mode and metadata conforms to standards."""

    @staticmethod
    def name():
        return "tap_tester_oracle_fusion_discovery_test"

    def streams_to_test(self):
        return self.expected_stream_names()

