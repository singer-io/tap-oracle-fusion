from tap_oracle_fusion.streams.abstracts import FullTableStream

class ReceivablesInvoices(FullTableStream):
    tap_stream_id = "receivables_invoices"
    key_properties = ["CustomerTransactionId"]
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "receivablesInvoices"
    children = "['attachments', 'notes']"

