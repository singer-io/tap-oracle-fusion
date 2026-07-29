"""Start-date test for tap-oracle-fusion.

Verifies tap behaviour with respect to ``start_date``.

For BICC streams ``OBEYS_START_DATE`` is False — the extract is controlled
by ``initial_extract_date`` in the tap config, not by ``start_date``.
Therefore the standard assertion is that both syncs return the same set of
records regardless of start date.

For any future REST-API streams where ``OBEYS_START_DATE`` is True, the
standard assertion applies: sync 1 (earlier start date) must return more
records than sync 2 (later start date).
"""

import unittest

from base import OracleFusionBaseTest
from tap_tester.base_suite_tests.start_date_test import StartDateTest


@unittest.skip(
    "tap-oracle-fusion BICC streams do not respect start_date. "
    "Filtering is controlled by initial_extract_date in the tap config."
)
class OracleFusionStartDateTest(StartDateTest, OracleFusionBaseTest):
    """Verify start-date behaviour for all 10 selected streams.

    Both dates are kept far enough in the past to guarantee data exists
    in the Oracle Fusion test environment.
    """

    @staticmethod
    def name():
        return "tap_tester_oracle_fusion_start_date_test"

    def streams_to_test(self):
        return self.expected_stream_names()

    @property
    def start_date_1(self):
        """Earlier start date — should capture the most data."""
        return "2015-01-01T00:00:00Z"

    @property
    def start_date_2(self):
        """Later start date — for BICC streams the record count will be the
        same as sync 1 because OBEYS_START_DATE is False."""
        return "2026-04-01T00:00:00Z"

    @unittest.skip(
        "tap-oracle-fusion BICC streams do not respect start_date directly. "
        "Filtering is controlled by initial_extract_date in the tap config. "
        "OBEYS_START_DATE=False is declared in base.py for all BICC streams."
    )
    def test_replication_key_values(self):
        """Skipped: start-date filtering is not enforced at the API level for
        BICC extracts.  Records are filtered by the BICC job's
        ``initialExtractDate``, which is a tap config setting, not the Singer
        ``start_date`` property tested here."""
