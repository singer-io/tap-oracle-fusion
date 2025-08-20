from tap_oracle_fusion.streams.abstracts import FullTableStream

class Erpintegrations(FullTableStream):
    tap_stream_id = "erpintegrations"
    key_properties = []
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "erpintegrations"

