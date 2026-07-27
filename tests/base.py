"""Base test class for tap-oracle-fusion integration tests.

Credentials are read from environment variables:
    TAP_ORACLE_FUSION_BASE_URL   - Oracle Fusion instance URL
    TAP_ORACLE_FUSION_USERNAME   - Basic-auth username
    TAP_ORACLE_FUSION_PASSWORD   - Basic-auth password

All 10 selected streams are BICC datastores sourced from catalog_500.json.
BICC syncs write a ``bicc_job_id`` entry to state (not a replication-key
value), so tests that rely on standard bookmark state must account for this
difference (see test_bookmark.py for the custom implementation).
"""

import os

from tap_tester.base_suite_tests.base_case import BaseCase


class OracleFusionBaseTest(BaseCase):
    """Setup expectations for tap-oracle-fusion integration test sub-classes.

    Provides tap-specific metadata for the 10 representative datastores
    selected for integration testing.
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
        the test does not trigger a full discovery run across all datastores.
        """
        return {
            "base_url": os.getenv(
                "TAP_ORACLE_FUSION_BASE_URL",
                "https://fa-eqkg-dev19-saasfademo1.ds-fa.oraclepdemos.com",
            ),
            "start_date": self.start_date,
            "parent_resource_groups": ["FscmTopModelAM"],
            "discovery_workers": 8,
            "discovery_limit": 500,
            "datastore_page_size": 500,
            # Restrict discovery to only the streams under test.
            "streams": list(self._selected_datastore_names()),
        }

    # ---------------------------------------------------------------------------
    # Stream metadata
    # ---------------------------------------------------------------------------

    @classmethod
    def expected_metadata(cls):
        """Expected stream names and their Singer / tap-tester metadata.


        ``OBEYS_START_DATE`` is False for all BICC streams because BICC
        extracts are gated by ``initial_extract_date`` in the tap config,
        not by the ``start_date`` property used in the Singer spec.
        """
        return {
            # ------------------------------------------------------------------
            # Purchase Orders — INCREMENTAL, single PK
            # ------------------------------------------------------------------
            "fscmtopmodelam_prcpopublicviewam_standardheaderpvo": {
                cls.PRIMARY_KEYS: {"PoHeaderId"},
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: {"POSystemParametersLastUpdateDate"},
                cls.OBEYS_START_DATE: False,
            },
            # ------------------------------------------------------------------
            # Purchasing Document Type — INCREMENTAL, compound PK (4 fields)
            # ------------------------------------------------------------------
            "fscmtopmodelam_prcpopublicviewam_purchasingdocumenttypebp": {
                cls.PRIMARY_KEYS: {
                    "DocumentSubtype",
                    "DocumentTypeCode",
                    "PODocumentTypeTransLanguage",
                    "PrcBuId",
                },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: {"PODocumentTypeLastUpdateDate"},
                cls.OBEYS_START_DATE: False,
            },
            # ------------------------------------------------------------------
            # Finance — Legal Entity & Ledger — INCREMENTAL, single PK
            # ------------------------------------------------------------------
            "fscmtopmodelam_finlelegalentitiesam_legalentitypvo": {
                cls.PRIMARY_KEYS: {"LegalEntityId"},
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: {"LegalEntityLastUpdateDate"},
                cls.OBEYS_START_DATE: False,
            },
            "fscmtopmodelam_finglledgerdefnam_ledgerpvo": {
                cls.PRIMARY_KEYS: {"LedgerId"},
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: {"LedgerLastUpdateDate"},
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
        These values are sourced directly from catalog_500.json.
        """
        return [
            "FscmTopModelAM.PrcPoPublicViewAM.StandardHeaderPVO",
            "FscmTopModelAM.PrcPoPublicViewAM.PurchasingDocumentTypeBP",
            "FscmTopModelAM.FinLeLegalEntitiesAM.LegalEntityPVO",
            "FscmTopModelAM.FinGlLedgerDefnAM.LedgerPVO",
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
