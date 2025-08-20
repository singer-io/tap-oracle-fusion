from tap_oracle_fusion.streams.abstracts import FullTableStream

class DebitAuthorizations(FullTableStream):
    tap_stream_id = "debit_authorizations"
    key_properties = ["DebitAuthorizationReferenceNumber"]
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "debitAuthorizations"

