from tap_oracle_fusion.streams.abstracts import ChildBaseStream

class FedGroupBudgetLevels(ChildBaseStream):
    tap_stream_id = "fed_group_budget_levels"
    key_properties = ["GroupBeLevelId"]
    replication_method = "INCREMENTAL"
    replication_keys = ["CreationDate"]
    data_key = "items"
    path = "fedGroups/{LedgerGroupId}/child/fedGroupBudgetLevels"
    parent = "fed_groups"
    bookmark_value = None

