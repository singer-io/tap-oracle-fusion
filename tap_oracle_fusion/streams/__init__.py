from tap_oracle_fusion.streams.bank_accounts import BankAccounts
from tap_oracle_fusion.streams.cash_bank_account_dff import CashBankAccountDff
from tap_oracle_fusion.streams.bank_account_payment_documents import BankAccountPaymentDocuments
from tap_oracle_fusion.streams.cash_bank_branches import CashBankBranches
from tap_oracle_fusion.streams.cash_banks import CashBanks
from tap_oracle_fusion.streams.brazilian_fiscal_documents import BrazilianFiscalDocuments
from tap_oracle_fusion.streams.cash_pools import CashPools
from tap_oracle_fusion.streams.cash_pool_members import CashPoolMembers
from tap_oracle_fusion.streams.collection_strategies import CollectionStrategies
from tap_oracle_fusion.streams.tasks import Tasks
from tap_oracle_fusion.streams.currency_rates import CurrencyRates
from tap_oracle_fusion.streams.data_securities import DataSecurities
from tap_oracle_fusion.streams.debit_authorizations import DebitAuthorizations
from tap_oracle_fusion.streams.erpintegrations import Erpintegrations
from tap_oracle_fusion.streams.expenses import Expenses
from tap_oracle_fusion.streams.expenses_attachments import ExpensesAttachments
from tap_oracle_fusion.streams.external_bank_accounts import ExternalBankAccounts
from tap_oracle_fusion.streams.account_owners import AccountOwners
from tap_oracle_fusion.streams.fed_groups import FedGroups
from tap_oracle_fusion.streams.fed_group_budget_levels import FedGroupBudgetLevels
from tap_oracle_fusion.streams.invoices import Invoices
from tap_oracle_fusion.streams.invoice import Invoice
from tap_oracle_fusion.streams.joint_ventures import JointVentures
from tap_oracle_fusion.streams.messages import Messages
from tap_oracle_fusion.streams.stakeholders import Stakeholders
from tap_oracle_fusion.streams.payables_payments import PayablesPayments
from tap_oracle_fusion.streams.related_invoices import RelatedInvoices
from tap_oracle_fusion.streams.receivables_invoices import ReceivablesInvoices
from tap_oracle_fusion.streams.attachments import Attachments
from tap_oracle_fusion.streams.notes import Notes
from tap_oracle_fusion.streams.tax_exemptions import TaxExemptions
from tap_oracle_fusion.streams.tax_registrations import TaxRegistrations

STREAMS = {
    "bank_accounts": BankAccounts,
    "cash_bank_account_dff": CashBankAccountDff,
    "bank_account_payment_documents": BankAccountPaymentDocuments,
    "cash_bank_branches": CashBankBranches,
    "cash_banks": CashBanks,
    "brazilian_fiscal_documents": BrazilianFiscalDocuments,
    "cash_pools": CashPools,
    "cash_pool_members": CashPoolMembers,
    "collection_strategies": CollectionStrategies,
    "tasks": Tasks,
    "currency_rates": CurrencyRates,
    "data_securities": DataSecurities,
    "debit_authorizations": DebitAuthorizations,
    "erpintegrations": Erpintegrations,
    "expenses": Expenses,
    "expenses_attachments": ExpensesAttachments,
    "external_bank_accounts": ExternalBankAccounts,
    "account_owners": AccountOwners,
    "fed_groups": FedGroups,
    "fed_group_budget_levels": FedGroupBudgetLevels,
    "invoices": Invoices,
    "invoice": Invoice,
    "joint_ventures": JointVentures,
    "messages": Messages,
    "stakeholders": Stakeholders,
    "payables_payments": PayablesPayments,
    "related_invoices": RelatedInvoices,
    "receivables_invoices": ReceivablesInvoices,
    "attachments": Attachments,
    "notes": Notes,
    "tax_exemptions": TaxExemptions,
    "tax_registrations": TaxRegistrations,
}

