from tap_oracle_fusion.streams.abstracts import FullTableStream

class CashBankBranches(FullTableStream):
    tap_stream_id = "cash_bank_branches"
    key_properties = ["BankPartyId"]
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "cashBankBranches"

