
from base import Oracle_fusionBaseTest
from tap_tester.base_suite_tests.interrupted_sync_test import InterruptedSyncTest


class Oracle_fusionInterruptedSyncTest(Oracle_fusionBaseTest):
    """Test tap sets a bookmark and respects it for the next sync of a
    stream."""

    @staticmethod
    def name():
        return "tap_tester_oracle_fusion_interrupted_sync_test"

    def streams_to_test(self):
        return self.expected_stream_names()


    def manipulate_state(self):
        return {
            "currently_syncing": "prospects",
            "bookmarks": {
                "bank_accounts": { "CreationDate" : "2020-01-01T00:00:00Z"},
                "bank_account_payment_documents": { "CreationDate" : "2020-01-01T00:00:00Z"},
                "cashBanks": { "CreationDate" : "2020-01-01T00:00:00Z"},
                "cash_pools": { "CreationDate" : "2020-01-01T00:00:00Z"},
                "cash_pool_members": { "CreationDate" : "2020-01-01T00:00:00Z"},
                "collection_strategies": { "CreationDate" : "2020-01-01T00:00:00Z"},
                "tasks": { "CreationDate" : "2020-01-01T00:00:00Z"},
                "fed_groups": { "CreationDate" : "2020-01-01T00:00:00Z"},
                "fed_group_budget_levels": { "CreationDate" : "2020-01-01T00:00:00Z"},
                "joint_ventures": { "CreationDate" : "2020-01-01T00:00:00Z"},
                "stakeholders": { "CreationDate" : "2020-01-01T00:00:00Z"},
                "payables_payments": { "CreationDate" : "2020-01-01T00:00:00Z"},
                "related_invoices": { "CreationDate" : "2020-01-01T00:00:00Z"},
        }
    }

