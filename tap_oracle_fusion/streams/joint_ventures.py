from tap_oracle_fusion.streams.abstracts import ParentBaseStream

class JointVentures(ParentBaseStream):
    tap_stream_id = "joint_ventures"
    key_properties = ["jointVentureId"]
    replication_method = "INCREMENTAL"
    replication_keys = ["CreationDate"]
    data_key = "items"
    path = "jointVentures"
    children = ["messages", "stakeholders"]

