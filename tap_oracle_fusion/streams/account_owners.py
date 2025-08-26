from tap_oracle_fusion.streams.abstracts import FullTableStream
from typing import Dict

class AccountOwners(FullTableStream):
    tap_stream_id = "account_owners"
    key_properties = ["AccountOwnerId"]
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "externalBankAccounts/{BankAccountId}/child/accountOwners"
    parent = "external_bank_accounts"
    
    
    def get_url_endpoint(self, parent_obj: Dict = None) -> str:
        """Constructs the API endpoint URL for fetching account owners for a given account number."""
        if not parent_obj or 'BankAccountNumber' not in parent_obj:
            raise ValueError("parent_obj must be provided with an 'BankAccountNumber' key.")
        return f"{self.client.base_url}/{self.path.format(BankAccountId = parent_obj['BankAccountNumber'])}"
