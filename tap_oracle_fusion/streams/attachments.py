from tap_oracle_fusion.streams.abstracts import FullTableStream
from typing import Dict

class Attachments(FullTableStream):
    tap_stream_id = "attachments"
    key_properties = []
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "receivablesInvoices/{CustomerTransactionId}/child/attachments"
    parent = "receivables_invoices"


    def get_url_endpoint(self, parent_obj: Dict = None) -> str:
        """Constructs the API endpoint URL for fetching attachments for a given customer transaction id."""
        if not parent_obj or 'CustomerTransactionId' not in parent_obj:
            raise ValueError("parent_obj must be provided with an 'CustomerTransactionId' key.")
        return f"{self.client.base_url}/{self.path.format(CustomerTransactionId = parent_obj['CustomerTransactionId'])}"
