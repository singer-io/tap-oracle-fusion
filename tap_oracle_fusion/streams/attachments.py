from tap_oracle_fusion.streams.abstracts import FullTableStream

class Attachments(FullTableStream):
    tap_stream_id = "attachments"
    key_properties = []
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "receivablesInvoices/{CustomerTransactionId}/child/attachments"
    path = "receivables_invoices"

