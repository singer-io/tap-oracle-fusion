import unittest
from unittest import mock

from tap_oracle_fusion.client import OracleClient, OracleClientError


class _FakeResponse:
    def __init__(self, status_code, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}


class TestOracleClient(unittest.TestCase):
    def test_resolve_base_url_prefers_explicit_base_url(self):
        config = {"base_url": "https://example.oracle.com/"}
        self.assertEqual(OracleClient._resolve_base_url(config), "https://example.oracle.com")

    def test_resolve_base_url_raises_when_insufficient_config(self):
        with self.assertRaises(OracleClientError):
            OracleClient._resolve_base_url({})

    def test_raise_for_http_error_429_sets_retry_after(self):
        response = _FakeResponse(429, text="Too many requests", headers={"Retry-After": "7"})

        with self.assertRaises(OracleClientError) as exc_ctx:
            OracleClient._raise_for_http_error(response)

        self.assertEqual(str(exc_ctx.exception), "Rate limit exceeded")
        self.assertEqual(getattr(exc_ctx.exception, "retry_after", None), 7)

    def test_raise_for_http_error_500_not_supported_is_non_retryable(self):
        response = _FakeResponse(
            500,
            text='{"message":"Data store X is not supported for extract"}',
        )

        with self.assertRaises(OracleClientError) as exc_ctx:
            OracleClient._raise_for_http_error(response)

        self.assertFalse(exc_ctx.exception.retryable)

    def test_raise_for_http_error_500_generic_is_retryable(self):
        response = _FakeResponse(500, text="temporary backend issue")

        with self.assertRaises(OracleClientError) as exc_ctx:
            OracleClient._raise_for_http_error(response)

        self.assertTrue(exc_ctx.exception.retryable)

    def test_raise_for_http_error_500_obis_page_unavailable_is_non_retryable(self):
        response = _FakeResponse(
            500,
            text="nQSError: 43113 Query Failed. Page Unavailable",
        )

        with self.assertRaises(OracleClientError) as exc_ctx:
            OracleClient._raise_for_http_error(response)

        self.assertFalse(exc_ctx.exception.retryable)

    def test_parse_next_link_extracts_path_and_query(self):
        payload = {
            "links": [
                {
                    "rel": "next",
                    "href": "https://host/hcmRestApi/resources/11.13.18.05/Workers?limit=50&offset=50",
                }
            ]
        }

        path, query = OracleClient.parse_next_link(payload)
        self.assertEqual(path, "hcmRestApi/resources/11.13.18.05/Workers")
        self.assertEqual(query, {"limit": "50", "offset": "50"})

    def test_extract_records_supports_bicc_datastores_key(self):
        payload = {
            "dataStores": [
                {"name": "Worker"},
                {"name": "Department"},
            ]
        }

        records = OracleClient._extract_records(payload)
        self.assertEqual(records, [{"name": "Worker"}, {"name": "Department"}])

    def test_get_records_uses_has_more_offset_pagination(self):
        config = {"base_url": "https://example", "page_size": 2}
        client = OracleClient(config)
        observed_params = []

        responses = [
            {
                "items": [{"id": 1}, {"id": 2}],
                "hasMore": True,
            },
            {
                "items": [{"id": 3}],
                "hasMore": False,
            },
        ]

        def _get_side_effect(path, params=None):
            observed_params.append(dict(params or {}))
            return responses[len(observed_params) - 1]

        with mock.patch.object(
            client,
            "get",
            side_effect=_get_side_effect,
        ) as mock_get:
            rows = list(client.get_records("hcmRestApi/resources/11.13.18.05/Workers"))

        self.assertEqual(rows, [{"id": 1}, {"id": 2}, {"id": 3}])
        first_call_args = mock_get.call_args_list[0][0]

        self.assertEqual(first_call_args[0], "hcmRestApi/resources/11.13.18.05/Workers")
        self.assertEqual(observed_params[0], {"limit": 2, "offset": 0})
        self.assertEqual(observed_params[1], {"limit": 2, "offset": 2})


if __name__ == "__main__":
    unittest.main()
