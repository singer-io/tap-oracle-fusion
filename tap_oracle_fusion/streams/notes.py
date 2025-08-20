from tap_oracle_fusion.streams.abstracts import FullTableStream

class Notes(FullTableStream):
    tap_stream_id = "notes"
    key_properties = []
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "receivablesInvoices/{CustomerTransactionId}/child/notes"
    path = "receivables_invoices"

