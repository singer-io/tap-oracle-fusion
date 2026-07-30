"""Additional tests for tap_oracle_fusion.client module."""
import time
import unittest
from unittest import mock

from tap_oracle_fusion.client import OracleClient, OracleClientError


class _FakeResponse:
    def __init__(self, status_code, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}

    def json(self):
        import json
        return json.loads(self.text)


class TestAuthMethods(unittest.TestCase):
    def test_auth_headers_returns_accept_json(self):
        client = OracleClient({"base_url": "https://example"})
        headers = client._auth_headers()
        self.assertEqual(headers["Accept"], "application/json")

    def test_auth_tuple_with_credentials(self):
        client = OracleClient(
            {"base_url": "https://example", "username": "user", "password": "pass"}
        )
        self.assertEqual(client._auth_tuple(), ("user", "pass"))

    def test_auth_tuple_without_credentials_returns_none(self):
        client = OracleClient({"base_url": "https://example"})
        self.assertIsNone(client._auth_tuple())

    def test_auth_tuple_with_only_username_returns_none(self):
        client = OracleClient({"base_url": "https://example", "username": "user"})
        self.assertIsNone(client._auth_tuple())


class TestExtractRetryAfterSeconds(unittest.TestCase):
    def test_returns_60_when_response_none(self):
        self.assertEqual(OracleClient._extract_retry_after_seconds(None), 60)

    def test_parses_retry_after_header(self):
        resp = _FakeResponse(429, headers={"Retry-After": "30"})
        self.assertEqual(OracleClient._extract_retry_after_seconds(resp), 30)

    def test_returns_60_on_invalid_header(self):
        resp = _FakeResponse(429, headers={"Retry-After": "not-a-number"})
        self.assertEqual(OracleClient._extract_retry_after_seconds(resp), 60)


class TestWaitIfRetryAfter(unittest.TestCase):
    @mock.patch("tap_oracle_fusion.client.time.sleep")
    def test_sleeps_when_retry_after_set(self, mock_sleep):
        exc = OracleClientError("Rate limited", retryable=True, retry_after=15)
        OracleClient._wait_if_retry_after({"exception": exc})
        mock_sleep.assert_called_once_with(15)

    @mock.patch("tap_oracle_fusion.client.time.sleep")
    def test_no_sleep_when_no_retry_after(self, mock_sleep):
        exc = OracleClientError("Server error", retryable=True)
        OracleClient._wait_if_retry_after({"exception": exc})
        mock_sleep.assert_not_called()


class TestShouldGiveUp(unittest.TestCase):
    def test_gives_up_on_non_retryable_oracle_error(self):
        exc = OracleClientError("not supported", retryable=False)
        self.assertTrue(OracleClient._should_give_up(exc))

    def test_does_not_give_up_on_retryable_oracle_error(self):
        exc = OracleClientError("temp error", retryable=True)
        self.assertFalse(OracleClient._should_give_up(exc))

    def test_does_not_give_up_on_non_oracle_error(self):
        self.assertFalse(OracleClient._should_give_up(ValueError("other")))


class TestIsNonRetryableServerError(unittest.TestCase):
    def test_not_supported_for_extract(self):
        self.assertTrue(
            OracleClient._is_non_retryable_server_error(
                '{"message":"Data store X is not supported for extract"}'
            )
        )

    def test_nqserror_43113(self):
        self.assertTrue(
            OracleClient._is_non_retryable_server_error("nQSError: 43113 something")
        )

    def test_prepare_query_failed(self):
        self.assertTrue(
            OracleClient._is_non_retryable_server_error("prepare query failed")
        )

    def test_page_unavailable(self):
        self.assertTrue(
            OracleClient._is_non_retryable_server_error("page unavailable error")
        )

    def test_generic_500_is_retryable(self):
        self.assertFalse(
            OracleClient._is_non_retryable_server_error("internal server error")
        )


class TestRaiseForHttpError(unittest.TestCase):
    def test_200_ok(self):
        # Should not raise
        OracleClient._raise_for_http_error(_FakeResponse(200))

    def test_201_ok(self):
        OracleClient._raise_for_http_error(_FakeResponse(201))

    def test_204_ok(self):
        OracleClient._raise_for_http_error(_FakeResponse(204))

    def test_401_raises_non_retryable(self):
        with self.assertRaises(OracleClientError) as ctx:
            OracleClient._raise_for_http_error(_FakeResponse(401, "Unauthorized"))
        self.assertFalse(ctx.exception.retryable)

    def test_403_raises_non_retryable(self):
        with self.assertRaises(OracleClientError) as ctx:
            OracleClient._raise_for_http_error(_FakeResponse(403, "Forbidden"))
        self.assertFalse(ctx.exception.retryable)


class TestExtractRecords(unittest.TestCase):
    def test_uses_items_key(self):
        self.assertEqual(OracleClient._extract_records({"items": [1, 2]}), [1, 2])

    def test_uses_data_key(self):
        self.assertEqual(OracleClient._extract_records({"data": [3, 4]}), [3, 4])

    def test_uses_results_key(self):
        self.assertEqual(OracleClient._extract_records({"results": [5]}), [5])

    def test_returns_empty_when_no_known_key(self):
        self.assertEqual(OracleClient._extract_records({"other": [1]}), [])


class TestParseNextLink(unittest.TestCase):
    def test_returns_none_when_no_links_key(self):
        self.assertIsNone(OracleClient.parse_next_link({}))

    def test_returns_none_when_links_not_list(self):
        self.assertIsNone(OracleClient.parse_next_link({"links": "not-a-list"}))

    def test_returns_none_when_no_next_rel(self):
        payload = {"links": [{"rel": "self", "href": "https://host/path"}]}
        self.assertIsNone(OracleClient.parse_next_link(payload))

    def test_returns_none_for_non_mapping_link(self):
        payload = {"links": ["not-a-mapping"]}
        self.assertIsNone(OracleClient.parse_next_link(payload))

    def test_returns_none_for_link_without_href(self):
        payload = {"links": [{"rel": "next"}]}
        self.assertIsNone(OracleClient.parse_next_link(payload))

    def test_returns_none_for_empty_href(self):
        payload = {"links": [{"rel": "next", "href": ""}]}
        self.assertIsNone(OracleClient.parse_next_link(payload))


class TestGetRecordsWithNextLink(unittest.TestCase):
    def test_follows_next_link_pagination(self):
        config = {"base_url": "https://example", "page_size": 2}
        client = OracleClient(config)
        call_count = [0]

        def fake_get(path, params=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return {
                    "items": [{"id": 1}],
                    "links": [
                        {
                            "rel": "next",
                            "href": "https://example/hcmRestApi/workers?limit=2&offset=2",
                        }
                    ],
                }
            return {"items": [{"id": 2}]}

        with mock.patch.object(client, "get", side_effect=fake_get):
            rows = list(client.get_records("hcmRestApi/workers"))

        self.assertEqual(rows, [{"id": 1}, {"id": 2}])
        self.assertEqual(call_count[0], 2)

    def test_skips_non_dict_records(self):
        config = {"base_url": "https://example"}
        client = OracleClient(config)

        def fake_get(path, params=None):
            return {"items": [{"id": 1}, "not-a-dict", {"id": 2}]}

        with mock.patch.object(client, "get", side_effect=fake_get):
            rows = list(client.get_records("some/path"))

        self.assertEqual(rows, [{"id": 1}, {"id": 2}])

    def test_raises_on_non_dict_json_response(self):
        """OracleClient.get raises when the JSON body is not a dict."""
        config = {"base_url": "https://example"}
        client = OracleClient(config)

        import json as _json

        class _ListResponse:
            status_code = 200
            text = _json.dumps([1, 2, 3])
            headers = {}

            def json(self):
                return [1, 2, 3]

        with mock.patch.object(client.session, "get", return_value=_ListResponse()):
            with self.assertRaises(OracleClientError) as ctx:
                client.get("some/path")
        self.assertIn("JSON object", str(ctx.exception))

    def test_get_returns_dict_payload_via_session(self):
        """OracleClient.get returns the dict payload on a successful call."""
        config = {"base_url": "https://example"}
        client = OracleClient(config)

        import json as _json

        class _DictResponse:
            status_code = 200
            text = _json.dumps({"items": []})
            headers = {}

            def json(self):
                return {"items": []}

        with mock.patch.object(client.session, "get", return_value=_DictResponse()):
            result = client.get("some/path")
        self.assertEqual(result, {"items": []})


if __name__ == "__main__":
    unittest.main()
