from tap_oracle_fusion.streams.abstracts import IncrementalStream

class Cashbanks(IncrementalStream):
    tap_stream_id = "cashBanks"
    key_properties = ["BankPartyId"]
    replication_method = "INCREMENTAL"
    replication_keys = ["CreationDate"]
    data_key = "items"
    path = "cashBanks"

