from tap_oracle_fusion.streams.abstracts import ParentBaseStream

class FedGroups(ParentBaseStream):
    tap_stream_id = "fed_groups"
    key_properties = ["LedgerGroupId"]
    replication_method = "INCREMENTAL"
    replication_keys = ["CreationDate"]
    data_key = "items"
    path = "fedGroups"
    children = ["fed_group_budget_levels"]

