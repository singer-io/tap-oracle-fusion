from tap_oracle_fusion.streams.abstracts import FullTableStream
from typing import Dict

class ExpensesAttachments(FullTableStream):
    tap_stream_id = "expenses_attachments"
    key_properties = ["AttachedDocumentId"]
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "expenses/{expensesUniqID}/child/Attachments"
    path = "expenses"
    
    
    def get_url_endpoint(self, parent_obj: Dict = None) -> str:
        """Constructs the API endpoint URL for fetching expenses attachments for a given expensesUniqID."""
        if not parent_obj or 'ExpenseId' not in parent_obj:
            raise ValueError("parent_obj must be provided with an 'ExpenseId' key.")
        return f"{self.client.base_url}/{self.path.format(expensesUniqID = parent_obj['ExpenseId'])}"


