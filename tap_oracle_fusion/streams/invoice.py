from tap_oracle_fusion.streams.abstracts import FullTableStream

class Invoice(FullTableStream):
    tap_stream_id = "invoice"
    key_properties = ["InvoiceId"]
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "invoice"
    path = "invoices"

