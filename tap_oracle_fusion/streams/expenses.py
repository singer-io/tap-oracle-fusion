from tap_oracle_fusion.streams.abstracts import FullTableStream

class Expenses(FullTableStream):
    tap_stream_id = "expenses"
    key_properties = ["ExpenseId"]
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "expenses"
    children = "['expenses_attachments']"

