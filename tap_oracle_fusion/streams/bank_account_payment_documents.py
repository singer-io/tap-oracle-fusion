from tap_oracle_fusion.streams.abstracts import ChildBaseStream

class BankAccountPaymentDocuments(ChildBaseStream):
    tap_stream_id = "bank_account_payment_documents"
    key_properties = ["PaymentDocumentId"]
    replication_method = "INCREMENTAL"
    replication_keys = ["CreationDate"]
    data_key = "items"
    path = "cashBankAccounts/{BankAccountId}/child/bankAccountPaymentDocuments"
    parent = "bank_accounts"
    bookmark_value = None

