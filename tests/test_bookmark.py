from base import Oracle_fusionBaseTest
from tap_tester.base_suite_tests.bookmark_test import BookmarkTest


class Oracle_fusionBookMarkTest(BookmarkTest, Oracle_fusionBaseTest):
    """Test tap sets a bookmark and respects it for the next sync of a
    stream."""
    bookmark_format = "%Y-%m-%dT%H:%M:%S.%fZ"
    initial_bookmarks = {
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
    @staticmethod
    def name():
        return "tap_tester_oracle_fusion_bookmark_test"

    def streams_to_test(self):
        streams_to_exclude = {}
        return self.expected_stream_names().difference(streams_to_exclude)

