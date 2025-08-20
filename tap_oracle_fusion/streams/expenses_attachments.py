from tap_oracle_fusion.streams.abstracts import FullTableStream

class ExpensesAttachments(FullTableStream):
    tap_stream_id = "expenses_attachments"
    key_properties = ["AttachedDocumentId"]
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "expenses/{expensesUniqID}/child/Attachments"
    path = "expenses"

