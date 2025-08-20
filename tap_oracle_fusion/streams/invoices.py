from tap_oracle_fusion.streams.abstracts import FullTableStream

class Invoices(FullTableStream):
    tap_stream_id = "invoices"
    key_properties = ["InvoiceId"]
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "invoices"
    children = "['invoice']"

