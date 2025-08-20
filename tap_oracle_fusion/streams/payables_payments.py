from tap_oracle_fusion.streams.abstracts import ParentBaseStream

class PayablesPayments(ParentBaseStream):
    tap_stream_id = "payables_payments"
    key_properties = ["PaymentId"]
    replication_method = "INCREMENTAL"
    replication_keys = ["CreationDate"]
    data_key = "items"
    path = "payablesPayments"
    children = ["related_invoices"]

