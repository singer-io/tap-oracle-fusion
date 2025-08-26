from tap_oracle_fusion.streams.abstracts import ChildBaseStream
from typing import Dict

class Stakeholders(ChildBaseStream):
    tap_stream_id = "stakeholders"
    key_properties = ["stakeholderId"]
    replication_method = "INCREMENTAL"
    replication_keys = ["CreationDate"]
    data_key = "items"
    path = "jointVentures/{jointVentureId}/child/stakeholders"
    parent = "joint_ventures"
    bookmark_value = None
    
    
    def get_url_endpoint(self, parent_obj: Dict = None) -> str:
        """Constructs the API endpoint URL for fetching stakeholders for a given jointVentureId."""
        if not parent_obj or 'jointVentureId' not in parent_obj:
            raise ValueError("parent_obj must be provided with an 'jointVentureId' key.")
        return f"{self.client.base_url}/{self.path.format(role_id = parent_obj['jointVentureId'])}"


