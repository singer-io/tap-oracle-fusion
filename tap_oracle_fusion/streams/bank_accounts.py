from tap_oracle_fusion.streams.abstracts import ParentBaseStream

class BankAccounts(ParentBaseStream):
    tap_stream_id = "bank_accounts"
    key_properties = ["BankAccountId"]
    replication_method = "INCREMENTAL"
    replication_keys = ["LastUpdateDate"]
    data_key = "items"
    path = "cashBankAccounts"
    children = ["cash_bank_account_dff", "bank_account_payment_documents"]

