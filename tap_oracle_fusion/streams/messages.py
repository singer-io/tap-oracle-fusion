from tap_oracle_fusion.streams.abstracts import FullTableStream

class Messages(FullTableStream):
    tap_stream_id = "messages"
    key_properties = []
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "jointVentures/{jointVentureId}/child/messages"
    path = "joint_ventures"

