"""Start-date test for tap-oracle-fusion.

Verifies tap behaviour with respect to ``start_date``.
"""

from base import OracleFusionBaseTest
from tap_tester.base_suite_tests.start_date_test import StartDateTest


class OracleFusionStartDateTest(StartDateTest, OracleFusionBaseTest):
    """Verify start-date behaviour for selected streams.

    Both dates are kept far enough in the past to guarantee data exists
    in the Oracle Fusion test environment.
    """

    @staticmethod
    def name():
        return "tap_tester_oracle_fusion_start_date_test"

    def streams_to_test(self):
        streams_to_exclude = {
            'fscmtopmodelam_prcpopublicviewam_standardheaderpvo',
            'fscmtopmodelam_finlelegalentitiesam_legalentitypvo',
        }
        return self.expected_stream_names().difference(streams_to_exclude)

    @property
    def start_date_1(self):
        return "2021-02-01T00:00:00Z"

    @property
    def start_date_2(self):
        return "2026-02-12T00:00:00Z"
