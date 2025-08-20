from tap_oracle_fusion.streams.abstracts import FullTableStream

class DataSecurities(FullTableStream):
    tap_stream_id = "data_securities"
    key_properties = ["UserRoleDataAssignmentId"]
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "dataSecurities"

