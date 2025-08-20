from tap_oracle_fusion.streams.abstracts import FullTableStream

class AccountOwners(FullTableStream):
    tap_stream_id = "account_owners"
    key_properties = ["AccountOwnerId"]
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "externalBankAccounts/{BankAccountId}/child/accountOwners"
    path = "external_bank_accounts"

