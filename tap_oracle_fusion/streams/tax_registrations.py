from tap_oracle_fusion.streams.abstracts import FullTableStream

class TaxRegistrations(FullTableStream):
    tap_stream_id = "tax_registrations"
    key_properties = ["RegistrationId"]
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "taxRegistrations"

