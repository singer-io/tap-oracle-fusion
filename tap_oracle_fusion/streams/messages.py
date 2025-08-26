from tap_oracle_fusion.streams.abstracts import FullTableStream
from typing import Dict

class Messages(FullTableStream):
    tap_stream_id = "messages"
    key_properties = []
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "jointVentures/{jointVentureId}/child/messages"
    path = "joint_ventures"
    
    
    def get_url_endpoint(self, parent_obj: Dict = None) -> str:
        """Constructs the API endpoint URL for fetching directory role member for a given jointVentureId."""
        if not parent_obj or 'jointVentureId' not in parent_obj:
            raise ValueError("parent_obj must be provided with an 'jointVentureId' key.")
        return f"{self.client.base_url}/{self.path.format(jointVentureId = parent_obj['jointVentureId'])}"


