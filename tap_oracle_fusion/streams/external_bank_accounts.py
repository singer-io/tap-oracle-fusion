from tap_oracle_fusion.streams.abstracts import FullTableStream

class ExternalBankAccounts(FullTableStream):
    tap_stream_id = "external_bank_accounts"
    key_properties = ["BankAccountNumber"]
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "externalBankAccounts"
    children = "['account_owners']"

