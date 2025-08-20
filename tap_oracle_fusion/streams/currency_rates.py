from tap_oracle_fusion.streams.abstracts import FullTableStream

class CurrencyRates(FullTableStream):
    tap_stream_id = "currency_rates"
    key_properties = []
    replication_method = "FULL_TABLE"
    data_key = "items"
    path = "currencyRates"

