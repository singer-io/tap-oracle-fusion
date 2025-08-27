from tap_oracle_fusion.streams.abstracts import ChildBaseStream
from typing import Dict

class FedGroupBudgetLevels(ChildBaseStream):
    tap_stream_id = "fed_group_budget_levels"
    key_properties = ["GroupBeLevelId"]
    replication_method = "INCREMENTAL"
    replication_keys = ["CreationDate"]
    data_key = "items"
    path = "fedGroups/{LedgerGroupId}/child/fedGroupBudgetLevels"
    parent = "fed_groups"
    bookmark_value = None
    
    
    def get_url_endpoint(self, parent_obj: Dict = None) -> str:
        """Constructs the API endpoint URL for fetching fed group budget Levels for a given LedgerGroupId."""
        if not parent_obj or 'LedgerGroupId' not in parent_obj:
            raise ValueError("parent_obj must be provided with an 'LedgerGroupId' key.")
        return f"{self.client.base_url}/{self.path.format(LedgerGroupId = parent_obj['LedgerGroupId'])}"


