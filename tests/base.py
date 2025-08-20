import copy
import os
import unittest
from datetime import datetime as dt
from datetime import timedelta

import dateutil.parser
import pytz
from tap_tester import connections, menagerie, runner
from tap_tester.logger import LOGGER
from tap_tester.base_suite_tests.base_case import BaseCase


class Oracle_fusionBaseTest(BaseCase):
    """Setup expectations for test sub classes.

    Metadata describing streams. A bunch of shared methods that are used
    in tap-tester tests. Shared tap-specific methods (as needed).
    """
    start_date = "2019-01-01T00:00:00Z"

    @staticmethod
    def tap_name():
        """The name of the tap."""
        return "tap-oracle_fusion"

    @staticmethod
    def get_type():
        """The name of the tap."""
        return "platform.oracle_fusion"

    @classmethod
    def expected_metadata(cls):
        """The expected streams and metadata about the streams."""
        return {
            "bank_accounts": {
                cls.PRIMARY_KEYS: { "BankAccountId" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "CreationDate, LastUpdateDate" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "cash_bank_account_dff": {
                cls.PRIMARY_KEYS: { "BankAccountId" },
                cls.REPLICATION_METHOD: cls.FULL_TABLE,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "bank_account_payment_documents": {
                cls.PRIMARY_KEYS: { "PaymentDocumentId" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "CreationDate" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "cash_bank_branches": {
                cls.PRIMARY_KEYS: { "BankPartyId" },
                cls.REPLICATION_METHOD: cls.FULL_TABLE,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "cashBanks": {
                cls.PRIMARY_KEYS: { "BankPartyId" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "CreationDate" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "brazilian_fiscal_documents": {
                cls.PRIMARY_KEYS: { "DocumentRelationId" },
                cls.REPLICATION_METHOD: cls.FULL_TABLE,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "cash_pools": {
                cls.PRIMARY_KEYS: { "CashPoolId" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "CreationDate, LastUpdateDate" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "cash_pool_members": {
                cls.PRIMARY_KEYS: { "CashPoolMemberId" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "CreationDate, LastUpdateDate" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "collection_strategies": {
                cls.PRIMARY_KEYS: { "StrategyId" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "CreationDate, LastUpdateDate" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "tasks": {
                cls.PRIMARY_KEYS: { "WorkItemId" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "CreationDate" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "currency_rates": {
                cls.PRIMARY_KEYS: { "" },
                cls.REPLICATION_METHOD: cls.FULL_TABLE,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "data_securities": {
                cls.PRIMARY_KEYS: { "UserRoleDataAssignmentId" },
                cls.REPLICATION_METHOD: cls.FULL_TABLE,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "debit_authorizations": {
                cls.PRIMARY_KEYS: { "DebitAuthorizationReferenceNumber" },
                cls.REPLICATION_METHOD: cls.FULL_TABLE,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "erpintegrations": {
                cls.PRIMARY_KEYS: { "" },
                cls.REPLICATION_METHOD: cls.FULL_TABLE,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "expenses": {
                cls.PRIMARY_KEYS: { "ExpenseId" },
                cls.REPLICATION_METHOD: cls.FULL_TABLE,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "expenses_attachments": {
                cls.PRIMARY_KEYS: { "AttachedDocumentId" },
                cls.REPLICATION_METHOD: cls.FULL_TABLE,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "external_bank_accounts": {
                cls.PRIMARY_KEYS: { "BankAccountNumber" },
                cls.REPLICATION_METHOD: cls.FULL_TABLE,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "account_owners": {
                cls.PRIMARY_KEYS: { "AccountOwnerId" },
                cls.REPLICATION_METHOD: cls.FULL_TABLE,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "fed_groups": {
                cls.PRIMARY_KEYS: { "LedgerGroupId" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "CreationDate" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "fed_group_budget_levels": {
                cls.PRIMARY_KEYS: { "GroupBeLevelId" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "CreationDate" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "invoices": {
                cls.PRIMARY_KEYS: { "InvoiceId" },
                cls.REPLICATION_METHOD: cls.FULL_TABLE,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "invoice": {
                cls.PRIMARY_KEYS: { "InvoiceId" },
                cls.REPLICATION_METHOD: cls.FULL_TABLE,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "joint_ventures": {
                cls.PRIMARY_KEYS: { "jointVentureId" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "CreationDate" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "messages": {
                cls.PRIMARY_KEYS: { "" },
                cls.REPLICATION_METHOD: cls.FULL_TABLE,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "stakeholders": {
                cls.PRIMARY_KEYS: { "stakeholderId" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "CreationDate" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "payables_payments": {
                cls.PRIMARY_KEYS: { "PaymentId" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "CreationDate" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "related_invoices": {
                cls.PRIMARY_KEYS: { "InvoicePaymentId" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "CreationDate" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "receivables_invoices": {
                cls.PRIMARY_KEYS: { "CustomerTransactionId" },
                cls.REPLICATION_METHOD: cls.FULL_TABLE,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "attachments": {
                cls.PRIMARY_KEYS: { "" },
                cls.REPLICATION_METHOD: cls.FULL_TABLE,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "notes": {
                cls.PRIMARY_KEYS: { "" },
                cls.REPLICATION_METHOD: cls.FULL_TABLE,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "tax_exemptions": {
                cls.PRIMARY_KEYS: { "TaxExemptionId" },
                cls.REPLICATION_METHOD: cls.FULL_TABLE,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            },
            "tax_registrations": {
                cls.PRIMARY_KEYS: { "RegistrationId" },
                cls.REPLICATION_METHOD: cls.FULL_TABLE,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100
            }
        }

    @staticmethod
    def get_credentials():
        """Authentication information for the test account."""
        credentials_dict = {}
        creds = {'client_id': 'TAP_ORACLE_FUSION_CLIENT_ID', 'client_secret': 'TAP_ORACLE_FUSION_CLIENT_SECRET', 'refresh_token': 'TAP_ORACLE_FUSION_REFRESH_TOKEN', 'profiles': 'TAP_ORACLE_FUSION_PROFILES'}

        for cred in creds:
            credentials_dict[cred] = os.getenv(creds[cred])

        return credentials_dict

    def get_properties(self, original: bool = True):
        """Configuration of properties required for the tap."""
        return_value = {
            "start_date": "2022-07-01T00:00:00Z"
        }
        if original:
            return return_value

        return_value["start_date"] = self.start_date
        return return_value

