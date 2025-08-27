from tap_oracle_fusion.streams.abstracts import FullTableStream
from typing import Dict

class Notes(FullTableStream):
    tap_stream_id = "notes"
    key_properties = []
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "receivablesInvoices/{CustomerTransactionId}/child/notes"
    path = "receivables_invoices"
    
    
    def get_url_endpoint(self, parent_obj: Dict = None) -> str:
        """Constructs the API endpoint URL for fetching notes for a given CustomerTransactionId."""
        if not parent_obj or 'CustomerTransactionId' not in parent_obj:
            raise ValueError("parent_obj must be provided with a 'CustomerTransactionId' key.")
        return f"{self.client.base_url}/{self.path.format(CustomerTransactionId = parent_obj['CustomerTransactionId'])}"


