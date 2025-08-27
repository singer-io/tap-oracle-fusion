from tap_oracle_fusion.streams.abstracts import FullTableStream
from typing import Dict

class Invoice(FullTableStream):
    tap_stream_id = "invoice"
    key_properties = ["InvoiceId"]
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "invoice"
    parent = "invoices"
    
    
    def get_url_endpoint(self, parent_obj: Dict = None) -> str:
        """Constructs the API endpoint URL for fetching Invoice for a given InvoiceId."""
        if not parent_obj or 'InvoiceId' not in parent_obj:
            raise ValueError("parent_obj must be provided with an 'InvoiceId' key.")
        return f"{self.client.base_url}/{self.path.format(InvoiceId = parent_obj['InvoiceId'])}"


