from tap_oracle_fusion.streams.abstracts import FullTableStream

class TaxExemptions(FullTableStream):
    tap_stream_id = "tax_exemptions"
    key_properties = ["TaxExemptionId"]
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "taxExemptions"

