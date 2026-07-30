"""Discovery test for tap-oracle-fusion.

Verifies that running the tap in check mode produces the expected catalog
entries with correct metadata (primary keys, replication method, replication
keys, field inclusion) for all 10 selected streams.
"""

from base import OracleFusionBaseTest
from tap_tester.base_suite_tests.discovery_test import DiscoveryTest


class OracleFusionDiscoveryTest(DiscoveryTest, OracleFusionBaseTest):
    """Test tap discovery mode and metadata conforms to standards."""

    @staticmethod
    def name():
        return "tap_tester_oracle_fusion_discovery_test"

    def streams_to_test(self):
        return self.expected_stream_names()
