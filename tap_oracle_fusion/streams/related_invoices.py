from tap_oracle_fusion.streams.abstracts import ChildBaseStream
from typing import Dict

class RelatedInvoices(ChildBaseStream):
    tap_stream_id = "related_invoices"
    key_properties = ["InvoicePaymentId"]
    replication_method = "INCREMENTAL"
    replication_keys = ["CreationDate"]
    data_key = "items"
    path = "payablesPayments/{CheckId}/child/relatedInvoices"
    parent = "payables_payments"
    bookmark_value = None
    
    
    def get_url_endpoint(self, parent_obj: Dict = None) -> str:
        """Constructs the API endpoint URL for fetching directory role member for a given role."""
        if not parent_obj or 'CheckId' not in parent_obj:
            raise ValueError("parent_obj must be provided with an 'CheckId' key.")
        return f"{self.client.base_url}/{self.path.format(CheckId = parent_obj['CheckId'])}"


