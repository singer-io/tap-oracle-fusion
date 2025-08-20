from tap_oracle_fusion.streams.abstracts import ChildBaseStream

class Tasks(ChildBaseStream):
    tap_stream_id = "tasks"
    key_properties = ["WorkItemId"]
    replication_method = "INCREMENTAL"
    replication_keys = ["CreationDate"]
    data_key = "items"
    path = "collectionStrategies/{StrategyId}/child/strategyExecutionTasks"
    parent = "collection_strategies"
    bookmark_value = None

