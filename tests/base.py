"""Base test class for tap-oracle-fusion integration tests.

Credentials are read from environment variables:
    TAP_ORACLE_FUSION_BASE_URL   - Oracle Fusion instance URL
    TAP_ORACLE_FUSION_USERNAME   - Basic-auth username
    TAP_ORACLE_FUSION_PASSWORD   - Basic-auth password

All 10 selected streams are BICC datastores.  BICC syncs write a
``bicc_job_id`` entry to state (not a replication-key value), so tests
that rely on standard bookmark state must account for this difference
(see test_bookmark.py for the custom implementation).
"""

import os

from tap_tester.base_suite_tests.base_case import BaseCase


class OracleFusionBaseTest(BaseCase):
    """Setup expectations for tap-oracle-fusion integration test sub-classes.

    Provides tap-specific metadata for the 10 representative datastores
    selected for integration testing.  Additional datastores can be added
    to ``expected_metadata()`` with minimal effort.
    """

    # Default start date used across all test classes.
    start_date = "2020-01-01T00:00:00Z"

    # ---------------------------------------------------------------------------
    # Required BaseCase abstract methods
    # ---------------------------------------------------------------------------

    @staticmethod
    def tap_name():
        return "tap-oracle-fusion"

    @staticmethod
    def get_type():
        return "platform.oracle_fusion"

    @staticmethod
    def get_credentials():
        """Authentication information for the test account.

        Oracle Fusion uses HTTP Basic Auth.  Credentials are read from
        environment variables so they are never committed to source control.
        """
        return {
            "username": os.getenv("TAP_ORACLE_FUSION_USERNAME"),
            "password": os.getenv("TAP_ORACLE_FUSION_PASSWORD"),
        }

    def get_properties(self, original: bool = True):
        """Non-credential configuration properties required by the tap.

        ``start_date`` defaults to the class-level value so individual test
        classes can override it (e.g. StartDateTest sets two different dates).

        The ``streams`` key limits discovery to the 10 selected datastores so
        the test does not trigger a full discovery run across ~1 600 datastores.
        """
        return {
            "base_url": os.getenv("TAP_ORACLE_FUSION_BASE_URL", ""),
            "start_date": self.start_date,
            # Restrict discovery to only the streams under test.
            "streams": list(self._selected_datastore_names()),
        }

    # ---------------------------------------------------------------------------
    # Stream metadata
    # ---------------------------------------------------------------------------

    @classmethod
    def expected_metadata(cls):
        """Expected stream names and their Singer / tap-tester metadata.

        10 streams selected to cover:
          - AR Receivables  (INCREMENTAL, single PK)
          - XLA Subledger   (INCREMENTAL, compound PKs)
          - FA Fixed Assets (INCREMENTAL, compound PKs)
          - Service Request (INCREMENTAL, single PK)
          - Extensibility   (FULL_TABLE,  no PKs)

        ``OBEYS_START_DATE`` is False for all BICC streams because BICC
        extracts are gated by ``initial_extract_date`` in the tap config,
        not by the ``start_date`` property used in the Singer spec.
        """
        return {
            # ------------------------------------------------------------------
            # Accounts Receivable — INCREMENTAL
            # ------------------------------------------------------------------
            "fscmtopmodelam_finextractam_arbiccextractam_salescredittypeextractpvo": {
                cls.PRIMARY_KEYS: {"ArSalesCreditTypeSalesCreditTypeId"},
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: {"ArSalesCreditTypeLastUpdateDate"},
                cls.OBEYS_START_DATE: False,
            },
            "fscmtopmodelam_finextractam_arbiccextractam_transactionhistoryallextractpvo": {
                cls.PRIMARY_KEYS: {"TransactionHistoryAllTransactionHistoryId"},
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: {"TransactionHistoryAllLastUpdateDate"},
                cls.OBEYS_START_DATE: False,
            },
            # ------------------------------------------------------------------
            # XLA Subledger Journal — INCREMENTAL, compound PKs
            # ------------------------------------------------------------------
            "fscmtopmodelam_finextractam_xlabiccextractam_subledgerjournalheaderextractpvo": {
                cls.PRIMARY_KEYS: {
                    "JournalEntryHeaderAeHeaderId",
                    "JournalEntryHeaderApplicationId",
                },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: {"JournalEntryHeaderLastUpdateDate"},
                cls.OBEYS_START_DATE: False,
            },
            "fscmtopmodelam_finextractam_xlabiccextractam_subledgerjournallineextractpvo": {
                cls.PRIMARY_KEYS: {
                    "JournalEntryLineAeHeaderId",
                    "JournalEntryLineAeLineNum",
                    "JournalEntryLineApplicationId",
                },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: {"JournalEntryLineLastUpdateDate"},
                cls.OBEYS_START_DATE: False,
            },
            "fscmtopmodelam_finextractam_xlabiccextractam_subledgerjournaldistributionextractpvo": {
                cls.PRIMARY_KEYS: {
                    "JournalEntryDistributionAeHeaderId",
                    "JournalEntryDistributionApplicationId",
                    "JournalEntryDistributionRefAeHeaderId",
                    "JournalEntryDistributionTempLineNum",
                },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: {"JournalEntryDistributionLastUpdateDate"},
                cls.OBEYS_START_DATE: False,
            },
            # ------------------------------------------------------------------
            # Fixed Assets — INCREMENTAL, compound PKs
            # ------------------------------------------------------------------
            "fscmtopmodelam_finextractam_fabiccextractam_bookcontrolextractpvo": {
                cls.PRIMARY_KEYS: {"BookControlBookTypeCode"},
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: {"BookControlLastUpdateDate"},
                cls.OBEYS_START_DATE: False,
            },
            "fscmtopmodelam_finextractam_fabiccextractam_booksummaryextractpvo": {
                cls.PRIMARY_KEYS: {
                    "BookSummaryAssetId",
                    "BookSummaryBookTypeCode",
                    "BookSummaryPeriodCounter",
                },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: {"BookSummaryLastUpdateDate"},
                cls.OBEYS_START_DATE: False,
            },
            # ------------------------------------------------------------------
            # Service Request — INCREMENTAL
            # ------------------------------------------------------------------
            "fscmtopmodelam_servicerequestam_servicerequestanalyticspvounsecured": {
                cls.PRIMARY_KEYS: {"SrId"},
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: {"LastUpdateDate"},
                cls.OBEYS_START_DATE: False,
            },
            # ------------------------------------------------------------------
            # Extensibility custom objects — FULL_TABLE, no PKs
            # ------------------------------------------------------------------
            "fscmtopmodelam_fscmanalyticsextensibilityam_task_c": {
                cls.PRIMARY_KEYS: set(),
                cls.REPLICATION_METHOD: cls.FULL_TABLE,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
            },
            "fscmtopmodelam_fscmanalyticsextensibilityam_projectstatus_c": {
                cls.PRIMARY_KEYS: set(),
                cls.REPLICATION_METHOD: cls.FULL_TABLE,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
            },
        }

    # ---------------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------------

    @classmethod
    def _selected_datastore_names(cls):
        """Return the BICC datastore keys for streams in expected_metadata.

        The mapping from tap_stream_id back to the original datastore name is
        captured in the ``tap-oracle-fusion.datastore-key`` metadata field.
        This list is derived directly from the catalog so discovery is scoped to
        only the 10 streams under test.
        """
        return [
            "FscmTopModelAM.FinExtractAM.ArBiccExtractAM.SalesCreditTypeExtractPVO",
            "FscmTopModelAM.FinExtractAM.ArBiccExtractAM.TransactionHistoryAllExtractPVO",
            "FscmTopModelAM.FinExtractAM.XlaBiccExtractAM.SubledgerJournalHeaderExtractPVO",
            "FscmTopModelAM.FinExtractAM.XlaBiccExtractAM.SubledgerJournalLineExtractPVO",
            "FscmTopModelAM.FinExtractAM.XlaBiccExtractAM.SubledgerJournalDistributionExtractPVO",
            "FscmTopModelAM.FinExtractAM.FaBiccExtractAM.BookControlExtractPVO",
            "FscmTopModelAM.FinExtractAM.FaBiccExtractAM.BookSummaryExtractPVO",
            "FscmTopModelAM.ServiceRequestAM.ServiceRequestAnalyticsPVOUnsecured",
            "FscmTopModelAM.FscmAnalyticsExtensibilityAM.Task_c",
            "FscmTopModelAM.FscmAnalyticsExtensibilityAM.ProjectStatus_c",
        ]

    @classmethod
    def incremental_streams(cls):
        """Return stream names whose replication method is INCREMENTAL."""
        return {
            stream
            for stream, meta in cls.expected_metadata().items()
            if meta.get(cls.REPLICATION_METHOD) == cls.INCREMENTAL
        }

    @classmethod
    def full_table_streams(cls):
        """Return stream names whose replication method is FULL_TABLE."""
        return {
            stream
            for stream, meta in cls.expected_metadata().items()
            if meta.get(cls.REPLICATION_METHOD) == cls.FULL_TABLE
        }
