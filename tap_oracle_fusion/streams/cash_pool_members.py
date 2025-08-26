from tap_oracle_fusion.streams.abstracts import ChildBaseStream
from typing import Dict

class CashPoolMembers(ChildBaseStream):
    tap_stream_id = "cash_pool_members"
    key_properties = ["CashPoolMemberId"]
    replication_method = "INCREMENTAL"
    replication_keys = ["LastUpdateDate"]
    data_key = "items"
    path = "cashPools/{CashPoolId}/child/cashPoolMembers"
    parent = "cash_pools"
    bookmark_value = None
    
    
    def get_url_endpoint(self, parent_obj: Dict = None) -> str:
        """Constructs the API endpoint URL for fetching directory cash pool members for a given cash pool id."""
        if not parent_obj or 'CashPoolId' not in parent_obj:
            raise ValueError("parent_obj must be provided with an 'CashPoolId' key.")
        return f"{self.client.base_url}/{self.path.format(CashPoolId = parent_obj['CashPoolId'])}"


