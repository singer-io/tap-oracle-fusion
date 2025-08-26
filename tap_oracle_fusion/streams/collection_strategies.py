from tap_oracle_fusion.streams.abstracts import ParentBaseStream

class CollectionStrategies(ParentBaseStream):
    tap_stream_id = "collection_strategies"
    key_properties = ["StrategyId"]
    replication_method = "INCREMENTAL"
    replication_keys = ["LastUpdateDate"]
    data_key = "items"
    path = "collectionStrategies"
    children = ["tasks"]

