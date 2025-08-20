from tap_oracle_fusion.streams.abstracts import ChildBaseStream

class RelatedInvoices(ChildBaseStream):
    tap_stream_id = "related_invoices"
    key_properties = ["InvoicePaymentId"]
    replication_method = "INCREMENTAL"
    replication_keys = ["CreationDate"]
    data_key = "items"
    path = "relatedInvoices"
    parent = "payables_payments"
    bookmark_value = None

