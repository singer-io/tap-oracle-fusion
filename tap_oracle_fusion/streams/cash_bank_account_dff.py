from tap_oracle_fusion.streams.abstracts import FullTableStream

class CashBankAccountDff(FullTableStream):
    tap_stream_id = "cash_bank_account_dff"
    key_properties = ["BankAccountId"]
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "cashBankAccounts/{BankAccountId}/child/cashBankAccountDFF"
    path = "bank_accounts"

