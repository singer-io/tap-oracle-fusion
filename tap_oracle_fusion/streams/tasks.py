from tap_oracle_fusion.streams.abstracts import ChildBaseStream
from typing import Dict

class Tasks(ChildBaseStream):
    tap_stream_id = "tasks"
    key_properties = ["WorkItemId"]
    replication_method = "INCREMENTAL"
    replication_keys = ["CreationDate"]
    data_key = "items"
    path = "collectionStrategies/{StrategyId}/child/strategyExecutionTasks"
    parent = "collection_strategies"
    bookmark_value = None
    
    
    def get_url_endpoint(self, parent_obj: Dict = None) -> str:
        """Constructs the API endpoint URL for fetching tasks for a given StrategyId."""
        if not parent_obj or 'StrategyId' not in parent_obj:
            raise ValueError("parent_obj must be provided with an 'StrategyId' key.")
        return f"{self.client.base_url}/{self.path.format(StrategyId = parent_obj['StrategyId'])}"


