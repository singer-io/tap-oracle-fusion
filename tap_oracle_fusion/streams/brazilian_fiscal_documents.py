from tap_oracle_fusion.streams.abstracts import FullTableStream

class BrazilianFiscalDocuments(FullTableStream):
    tap_stream_id = "brazilian_fiscal_documents"
    key_properties = ["DocumentRelationId"]
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "brazilianFiscalDocuments"

