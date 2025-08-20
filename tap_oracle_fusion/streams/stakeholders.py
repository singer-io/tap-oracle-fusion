from tap_oracle_fusion.streams.abstracts import ChildBaseStream

class Stakeholders(ChildBaseStream):
    tap_stream_id = "stakeholders"
    key_properties = ["stakeholderId"]
    replication_method = "INCREMENTAL"
    replication_keys = ["CreationDate"]
    data_key = "items"
    path = "jointVentures/{jointVentureId}/child/stakeholders"
    parent = "joint_ventures"
    bookmark_value = None

