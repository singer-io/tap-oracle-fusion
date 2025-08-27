from tap_oracle_fusion.streams.abstracts import FullTableStream
from typing import Dict

class CashBankAccountDff(FullTableStream):
    tap_stream_id = "cash_bank_account_dff"
    key_properties = ["BankAccountId"]
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "cashBankAccounts/{BankAccountId}/child/cashBankAccountDFF"
    parent = "bank_accounts"
    
    
    def get_url_endpoint(self, parent_obj: Dict = None) -> str:
        """Constructs the API endpoint URL for fetching cash bank account dff for a given bank accounts."""
        if not parent_obj or 'BankAccountId' not in parent_obj:
            raise ValueError("parent_obj must be provided with an 'BankAccountId' key.")
        return f"{self.client.base_url}/{self.path.format(BankAccountId = parent_obj['BankAccountId'])}"


