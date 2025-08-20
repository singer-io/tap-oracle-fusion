from tap_oracle_fusion.streams.abstracts import ChildBaseStream

class CashPoolMembers(ChildBaseStream):
    tap_stream_id = "cash_pool_members"
    key_properties = ["CashPoolMemberId"]
    replication_method = "INCREMENTAL"
    replication_keys = ["CreationDate", "LastUpdateDate"]
    data_key = "items"
    path = "cashPools/{CashPoolId}/child/cashPoolMembers"
    parent = "cash_pools"
    bookmark_value = None

