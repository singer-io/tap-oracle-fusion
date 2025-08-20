from tap_oracle_fusion.streams.abstracts import ParentBaseStream

class CashPools(ParentBaseStream):
    tap_stream_id = "cash_pools"
    key_properties = ["CashPoolId"]
    replication_method = "INCREMENTAL"
    replication_keys = ["CreationDate", "LastUpdateDate"]
    data_key = "items"
    path = "cashPools"
    children = ["cash_pool_members"]

