from tap_oracle_fusion.streams.abstracts import ChildBaseStream
from typing import Dict

class BankAccountPaymentDocuments(ChildBaseStream):
    tap_stream_id = "bank_account_payment_documents"
    key_properties = ["PaymentDocumentId"]
    replication_method = "INCREMENTAL"
    replication_keys = ["CreationDate"]
    data_key = "items"
    path = "cashBankAccounts/{BankAccountId}/child/bankAccountPaymentDocuments"
    parent = "bank_accounts"
    bookmark_value = None
    
    
    def get_url_endpoint(self, parent_obj: Dict = None) -> str:
        """Constructs the API endpoint URL for fetching bank account payment documents for a given bank account."""
        if not parent_obj or 'BankAccountId' not in parent_obj:
            raise ValueError("parent_obj must be provided with an 'BankAccountId' key.")
        return f"{self.client.base_url}/{self.path.format(BankAccountId = parent_obj['BankAccountId'])}"
