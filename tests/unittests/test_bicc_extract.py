"""Tests for tap_oracle_fusion.bicc_extract module."""
import base64
import io
import json
import unittest
from unittest import mock
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import requests

from tap_oracle_fusion.bicc_extract import (
    BICCExtractClient,
    ExtractError,
    _as_int,
    _document_field,
    _envelope_and_attachments,
    _get_file_envelope,
    _iter_csv_rows_from_zip_bytes,
    _local,
    _search_envelope,
    _search_rows,
    _soap_fault,
    _split_multipart,
    _state_envelope,
    _submit_envelope,
    _submit_request_id,
    _text_by_local_name,
    _utc_now_iso,
    _utc_plus_seconds_iso,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_zip_bytes(csv_files: dict) -> bytes:
    """Return in-memory ZIP bytes containing the given {name: csv_text} entries."""
    buf = io.BytesIO()
    with ZipFile(buf, "w") as zf:
        for name, content in csv_files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _make_multipart_body(parts: list, boundary: str = "TESTBOUNDARY") -> tuple:
    """Return (body_bytes, content_type_header) for a synthetic multipart response."""
    body = b""
    for headers, content in parts:
        body += f"--{boundary}\r\n".encode()
        for k, v in headers.items():
            body += f"{k}: {v}\r\n".encode()
        body += b"\r\n"
        body += content
        body += b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    content_type = f'multipart/related; boundary="{boundary}"'
    return body, content_type


class _FakeResponse:
    def __init__(self, status_code=200, text="", content=None, headers=None):
        self.status_code = status_code
        self.text = text
        self.content = content if content is not None else text.encode()
        self.headers = headers or {}

    def json(self):
        return json.loads(self.text)


# ---------------------------------------------------------------------------
# Pure helper function tests
# ---------------------------------------------------------------------------

class TestLocalHelper(unittest.TestCase):
    def test_strips_namespace(self):
        self.assertEqual(_local("{http://schemas.xmlsoap.org/soap/envelope/}Body"), "Body")

    def test_no_namespace_unchanged(self):
        self.assertEqual(_local("faultstring"), "faultstring")


class TestAsInt(unittest.TestCase):
    def test_valid_string(self):
        self.assertEqual(_as_int("42"), 42)
        self.assertEqual(_as_int("  7  "), 7)

    def test_invalid_string(self):
        self.assertIsNone(_as_int("abc"))

    def test_none_input(self):
        self.assertIsNone(_as_int(None))


class TestUtcHelpers(unittest.TestCase):
    def test_utc_now_iso_format(self):
        result = _utc_now_iso()
        self.assertRegex(result, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")

    def test_utc_plus_seconds_iso_format(self):
        result = _utc_plus_seconds_iso(120)
        self.assertRegex(result, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


class TestTextByLocalName(unittest.TestCase):
    def test_found(self):
        xml = "<root><state>SUCCEEDED</state></root>"
        self.assertEqual(_text_by_local_name(xml, "state"), "SUCCEEDED")

    def test_not_found(self):
        xml = "<root><other>X</other></root>"
        self.assertIsNone(_text_by_local_name(xml, "state"))

    def test_empty_text_not_returned(self):
        xml = "<root><state>   </state></root>"
        self.assertIsNone(_text_by_local_name(xml, "state"))

    def test_invalid_xml_returns_none(self):
        self.assertIsNone(_text_by_local_name("<<not xml>>", "state"))


class TestSubmitRequestId(unittest.TestCase):
    def test_value_child_element(self):
        xml = "<root><requestId><value>12345</value></requestId></root>"
        self.assertEqual(_submit_request_id(xml), "12345")

    def test_direct_text(self):
        xml = "<root><requestId>99999</requestId></root>"
        self.assertEqual(_submit_request_id(xml), "99999")

    def test_not_found_returns_none(self):
        xml = "<root><other>X</other></root>"
        self.assertIsNone(_submit_request_id(xml))

    def test_invalid_xml_returns_none(self):
        self.assertIsNone(_submit_request_id("not xml <<"))


class TestDocumentField(unittest.TestCase):
    def test_found_by_name(self):
        xml = '<root><Field name="StatusCode">0</Field></root>'
        root = ET.fromstring(xml)
        self.assertEqual(_document_field(root, "StatusCode"), "0")

    def test_found_by_Name_attribute(self):
        xml = '<root><Field Name="StatusMessage">OK</Field></root>'
        root = ET.fromstring(xml)
        self.assertEqual(_document_field(root, "StatusMessage"), "OK")

    def test_not_found_returns_none(self):
        xml = '<root><Field name="Other">X</Field></root>'
        root = ET.fromstring(xml)
        self.assertIsNone(_document_field(root, "StatusCode"))


class TestSoapFault(unittest.TestCase):
    def test_fault_found(self):
        xml = "<root><faultstring>Auth failed</faultstring></root>"
        root = ET.fromstring(xml)
        self.assertEqual(_soap_fault(root), "Auth failed")

    def test_empty_faultstring_ignored(self):
        xml = "<root><faultstring>   </faultstring></root>"
        root = ET.fromstring(xml)
        self.assertIsNone(_soap_fault(root))

    def test_no_fault(self):
        xml = "<root><other>X</other></root>"
        root = ET.fromstring(xml)
        self.assertIsNone(_soap_fault(root))


class TestSearchRows(unittest.TestCase):
    def test_parses_rows_with_fields(self):
        xml = """<root>
            <Row>
                <Field name="dID">123</Field>
                <Field name="dDocTitle">file_worker</Field>
            </Row>
            <Row>
                <Field Name="dID">456</Field>
            </Row>
        </root>"""
        root = ET.fromstring(xml)
        rows = _search_rows(root)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["dID"], "123")
        self.assertEqual(rows[0]["dDocTitle"], "file_worker")
        self.assertEqual(rows[1]["dID"], "456")

    def test_skips_rows_without_did(self):
        xml = """<root><Row><Field name="dDocTitle">file</Field></Row></root>"""
        root = ET.fromstring(xml)
        self.assertEqual(_search_rows(root), [])

    def test_skips_empty_field_values(self):
        xml = """<root>
            <Row>
                <Field name="dID">100</Field>
                <Field name="dDocTitle"></Field>
            </Row>
        </root>"""
        root = ET.fromstring(xml)
        rows = _search_rows(root)
        self.assertEqual(len(rows), 1)
        self.assertNotIn("dDocTitle", rows[0])

    def test_skips_non_field_child_element_in_row(self):
        xml = """<root>
            <Row>
                <Field name="dID">999</Field>
                <Other name="ignored">value</Other>
                <Field name="dDocTitle">doc</Field>
            </Row>
        </root>"""
        root = ET.fromstring(xml)
        rows = _search_rows(root)
        self.assertEqual(len(rows), 1)
        self.assertNotIn("ignored", rows[0])
        self.assertEqual(rows[0]["dDocTitle"], "doc")


# ---------------------------------------------------------------------------
# _iter_csv_rows_from_zip_bytes
# ---------------------------------------------------------------------------

class TestIterCsvRowsFromZipBytes(unittest.TestCase):
    def test_basic_csv_rows(self):
        payload = _make_zip_bytes({"data.csv": "id,name\n1,Alice\n2,Bob\n"})
        rows = list(_iter_csv_rows_from_zip_bytes(payload))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], {"id": "1", "name": "Alice"})
        self.assertEqual(rows[1], {"id": "2", "name": "Bob"})

    def test_deduplicates_across_csv_files(self):
        payload = _make_zip_bytes({
            "file1.csv": "id,val\n1,a\n2,b\n",
            "file2.csv": "id,val\n2,b\n3,c\n",
        })
        rows = list(_iter_csv_rows_from_zip_bytes(payload))
        self.assertEqual(len(rows), 3)
        ids = [r["id"] for r in rows]
        self.assertIn("1", ids)
        self.assertIn("2", ids)
        self.assertIn("3", ids)

    def test_none_values_replaced_with_empty_string(self):
        payload = _make_zip_bytes({"data.csv": "id,name\n1,\n"})
        rows = list(_iter_csv_rows_from_zip_bytes(payload))
        self.assertEqual(rows[0]["name"], "")

    def test_non_csv_file_used_as_fallback(self):
        payload = _make_zip_bytes({"data.tsv": "id,val\n1,x\n"})
        rows = list(_iter_csv_rows_from_zip_bytes(payload))
        self.assertEqual(len(rows), 1)

    def test_bad_zip_raises_extract_error(self):
        with self.assertRaises(ExtractError) as ctx:
            list(_iter_csv_rows_from_zip_bytes(b"not a zip file"))
        self.assertIn("not a valid zip", str(ctx.exception))


# ---------------------------------------------------------------------------
# _split_multipart
# ---------------------------------------------------------------------------

class TestSplitMultipart(unittest.TestCase):
    def test_no_boundary_returns_none(self):
        self.assertIsNone(_split_multipart(b"some content", "text/plain"))

    def test_two_parts_parsed(self):
        xml_part = b"<envelope>main</envelope>"
        zip_part = b"PKfakezip12345"
        body, ct = _make_multipart_body([
            ({"content-type": "text/xml"}, xml_part),
            ({"content-type": "application/zip"}, zip_part),
        ])
        parts = _split_multipart(body, ct)
        self.assertIsNotNone(parts)
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0][0]["content-type"], "text/xml")
        self.assertEqual(parts[0][1], xml_part)
        self.assertEqual(parts[1][1], zip_part)

    def test_single_part_parsed(self):
        xml_part = b"<response/>"
        body, ct = _make_multipart_body([({"content-type": "text/xml"}, xml_part)])
        parts = _split_multipart(body, ct)
        self.assertIsNotNone(parts)
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0][1], xml_part)

    def test_boundary_without_quotes(self):
        xml_part = b"<root/>"
        body = b"--BOUND\r\ncontent-type: text/xml\r\n\r\n<root/>\r\n--BOUND--\r\n"
        ct = "multipart/related; boundary=BOUND"
        parts = _split_multipart(body, ct)
        self.assertIsNotNone(parts)
        self.assertEqual(len(parts), 1)

    def test_breaks_on_part_starting_with_dashes(self):
        # A second boundary occurrence whose content starts with '--' triggers the break.
        content = (
            b"--BOUND\r\n"
            b"content-type: text/xml\r\n"
            b"\r\n"
            b"<root/>\r\n"
            b"--BOUND\r\n"      # extra boundary occurrence in stream
            b"--BOUND--\r\n"   # immediately followed by final boundary
        )
        ct = "multipart/related; boundary=BOUND"
        parts = _split_multipart(content, ct)
        self.assertIsNotNone(parts)
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0][1], b"<root/>")

    def test_skips_part_with_no_header_separator(self):
        # A part with no \r\n\r\n header/body separator is skipped via continue.
        content = b"--BOUND\r\nno-double-crlf-here\r\n--BOUND--\r\n"
        ct = "multipart/related; boundary=BOUND"
        parts = _split_multipart(content, ct)
        self.assertEqual(parts, [])


# ---------------------------------------------------------------------------
# _envelope_and_attachments
# ---------------------------------------------------------------------------

class TestEnvelopeAndAttachments(unittest.TestCase):
    def test_no_parts_returns_content_as_envelope(self):
        resp = _FakeResponse(200, "<root/>")
        envelope, attachments = _envelope_and_attachments(resp)
        self.assertEqual(envelope, b"<root/>")
        self.assertEqual(attachments, [])

    def test_with_start_id_selects_correct_root(self):
        xml_part = b"<envelope>main</envelope>"
        zip_part = b"binary_data_here"
        body, base_ct = _make_multipart_body([
            ({"content-type": "application/zip", "content-id": "att1"}, zip_part),
            ({"content-type": "text/xml", "content-id": "root-env"}, xml_part),
        ])
        ct = base_ct + '; start="root-env"'
        resp = _FakeResponse(200, content=body, headers={"Content-Type": ct})
        envelope, attachments = _envelope_and_attachments(resp)
        self.assertEqual(envelope, xml_part)
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0][1], zip_part)

    def test_no_start_uses_first_part(self):
        xml_part = b"<envelope>main</envelope>"
        zip_part = b"binary_data"
        body, ct = _make_multipart_body([
            ({"content-type": "text/xml"}, xml_part),
            ({"content-type": "application/zip"}, zip_part),
        ])
        resp = _FakeResponse(200, content=body, headers={"Content-Type": ct})
        envelope, attachments = _envelope_and_attachments(resp)
        self.assertEqual(envelope, xml_part)
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0][1], zip_part)


# ---------------------------------------------------------------------------
# BICCExtractClient.__init__ and datastore_slug
# ---------------------------------------------------------------------------

class TestBICCExtractClientInit(unittest.TestCase):
    def test_init_attributes(self):
        config = {
            "base_url": "https://oracle.example.com/",
            "username": "user@example.com",
            "password": "secret",
            "request_timeout": 60,
        }
        client = BICCExtractClient(config)
        self.assertEqual(client.base_url, "https://oracle.example.com")
        self.assertEqual(client.username, "user@example.com")
        self.assertEqual(client.password, "secret")
        self.assertEqual(client.timeout, 60.0)
        self.assertIn("bi/ess/esswebservice", client.ess_url)
        self.assertIn("idcws/GenericSoapPort", client.ucm_url)

    def test_datastore_slug_lowercases_and_replaces_dots(self):
        self.assertEqual(BICCExtractClient.datastore_slug("Worker.Store"), "worker_store")

    def test_datastore_slug_strips_whitespace(self):
        self.assertEqual(BICCExtractClient.datastore_slug("  MyDS  "), "myds")


# ---------------------------------------------------------------------------
# create_bicc_job
# ---------------------------------------------------------------------------

class TestCreateBiccJob(unittest.TestCase):
    def _client(self):
        return BICCExtractClient(
            {"base_url": "https://example", "username": "u", "password": "p"}
        )

    @mock.patch("tap_oracle_fusion.bicc_extract.requests.put")
    def test_success(self, mock_put):
        mock_put.return_value = _FakeResponse(
            200, json.dumps({"status": "SUCCESS", "id": "job-123"})
        )
        job_id = self._client().create_bicc_job("W.DS", "2020-01-01T00:00:00.000")
        self.assertEqual(job_id, "job-123")

    @mock.patch("tap_oracle_fusion.bicc_extract.requests.put")
    def test_http_400_raises_extract_error(self, mock_put):
        mock_put.return_value = _FakeResponse(400, "bad request")
        with self.assertRaises(ExtractError) as ctx:
            self._client().create_bicc_job("W.DS", "2020-01-01T00:00:00.000")
        self.assertIn("create-job failed", str(ctx.exception))

    @mock.patch("tap_oracle_fusion.bicc_extract.requests.put")
    def test_non_json_body_raises(self, mock_put):
        mock_put.return_value = _FakeResponse(200, "not-json-at-all")
        with self.assertRaises(ExtractError):
            self._client().create_bicc_job("W.DS", "2020-01-01T00:00:00.000")

    @mock.patch("tap_oracle_fusion.bicc_extract.requests.put")
    def test_non_success_status_raises(self, mock_put):
        mock_put.return_value = _FakeResponse(
            200, json.dumps({"status": "FAILED", "id": "x"})
        )
        with self.assertRaises(ExtractError) as ctx:
            self._client().create_bicc_job("W.DS", "2020-01-01T00:00:00.000")
        self.assertIn("non-success", str(ctx.exception))

    @mock.patch("tap_oracle_fusion.bicc_extract.requests.put")
    def test_missing_id_raises(self, mock_put):
        mock_put.return_value = _FakeResponse(
            200, json.dumps({"status": "SUCCESS", "id": ""})
        )
        with self.assertRaises(ExtractError) as ctx:
            self._client().create_bicc_job("W.DS", "2020-01-01T00:00:00.000")
        self.assertIn("missing id", str(ctx.exception))

    @mock.patch("tap_oracle_fusion.bicc_extract.requests.put")
    def test_custom_job_name(self, mock_put):
        mock_put.return_value = _FakeResponse(
            200, json.dumps({"status": "SUCCESS", "id": "job-456"})
        )
        self._client().create_bicc_job("W.DS", "2020-01-01", job_name="my_custom")
        call_json = mock_put.call_args[1]["json"]
        self.assertEqual(call_json["name"], "my_custom")


# ---------------------------------------------------------------------------
# submit and poll
# ---------------------------------------------------------------------------

class TestSubmitAndPoll(unittest.TestCase):
    def _client(self):
        return BICCExtractClient(
            {"base_url": "https://example", "username": "u", "password": "p"}
        )

    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_submit_returns_request_id(self, mock_post):
        xml = "<root><requestId><value>REQ-001</value></requestId></root>"
        mock_post.return_value = _FakeResponse(200, xml)
        req_id = self._client().submit("W.DS", "job-1")
        self.assertEqual(req_id, "REQ-001")

    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_submit_raises_when_no_request_id(self, mock_post):
        fault_xml = "<root><faultstring>Auth failed</faultstring></root>"
        mock_post.return_value = _FakeResponse(200, fault_xml)
        with self.assertRaises(ExtractError) as ctx:
            self._client().submit("W.DS", "job-1")
        self.assertIn("missing requestId", str(ctx.exception))
        self.assertIn("Auth failed", str(ctx.exception))

    @mock.patch("tap_oracle_fusion.bicc_extract.time.sleep", return_value=None)
    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_poll_succeeded(self, mock_post, _sleep):
        mock_post.return_value = _FakeResponse(200, "<root><state>SUCCEEDED</state></root>")
        state = self._client().poll("REQ-001", poll_interval=0)
        self.assertEqual(state, "SUCCEEDED")

    @mock.patch("tap_oracle_fusion.bicc_extract.time.sleep", return_value=None)
    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_poll_warning_state_returned(self, mock_post, _sleep):
        mock_post.return_value = _FakeResponse(200, "<root><state>WARNING</state></root>")
        state = self._client().poll("REQ-001", poll_interval=0)
        self.assertEqual(state, "WARNING")

    @mock.patch("tap_oracle_fusion.bicc_extract.time.sleep", return_value=None)
    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_poll_continues_until_terminal(self, mock_post, _sleep):
        mock_post.side_effect = [
            _FakeResponse(200, "<root><state>RUNNING</state></root>"),
            _FakeResponse(200, "<root><state>RUNNING</state></root>"),
            _FakeResponse(200, "<root><state>SUCCEEDED</state></root>"),
        ]
        state = self._client().poll("REQ-001", poll_interval=0)
        self.assertEqual(state, "SUCCEEDED")
        self.assertEqual(mock_post.call_count, 3)

    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_poll_raises_on_missing_state(self, mock_post):
        mock_post.return_value = _FakeResponse(200, "<root><faultstring>bad</faultstring></root>")
        with self.assertRaises(ExtractError) as ctx:
            self._client().poll("REQ-001", poll_interval=0)
        self.assertIn("missing state", str(ctx.exception))

    @mock.patch("tap_oracle_fusion.bicc_extract.time.sleep", return_value=None)
    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_poll_sleeps_between_attempts(self, mock_post, mock_sleep):
        mock_post.side_effect = [
            _FakeResponse(200, "<root><state>RUNNING</state></root>"),
            _FakeResponse(200, "<root><state>SUCCEEDED</state></root>"),
        ]
        self._client().poll("REQ-001", poll_interval=10)
        mock_sleep.assert_called_once_with(10)


# ---------------------------------------------------------------------------
# _search_datastore_files, latest_did, find_file_id
# ---------------------------------------------------------------------------

class TestSearchAndFindFile(unittest.TestCase):
    def _client(self):
        return BICCExtractClient(
            {"base_url": "https://example", "username": "u", "password": "p"}
        )

    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_search_returns_rows(self, mock_post):
        xml = """<root>
            <Row><Field name="dID">100</Field></Row>
            <Row><Field name="dID">200</Field></Row>
        </root>"""
        mock_post.return_value = _FakeResponse(200, xml)
        rows = self._client()._search_datastore_files("W.DS")
        self.assertEqual(len(rows), 2)

    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_search_raises_on_soap_fault(self, mock_post):
        mock_post.return_value = _FakeResponse(200, "<root><faultstring>Auth error</faultstring></root>")
        with self.assertRaises(ExtractError) as ctx:
            self._client()._search_datastore_files("W.DS")
        self.assertIn("SOAP fault", str(ctx.exception))

    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_search_raises_on_status_code_error(self, mock_post):
        xml = "<root><Field name='StatusCode'>99</Field><Field name='StatusMessage'>Err</Field></root>"
        mock_post.return_value = _FakeResponse(200, xml)
        with self.assertRaises(ExtractError) as ctx:
            self._client()._search_datastore_files("W.DS")
        self.assertIn("StatusCode=99", str(ctx.exception))

    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_search_raises_on_parse_error(self, mock_post):
        mock_post.return_value = _FakeResponse(200, "not xml <<< broken")
        with self.assertRaises(ExtractError) as ctx:
            self._client()._search_datastore_files("W.DS")
        self.assertIn("unparseable", str(ctx.exception))

    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_latest_did_returns_max(self, mock_post):
        xml = """<root>
            <Row><Field name="dID">100</Field></Row>
            <Row><Field name="dID">300</Field></Row>
            <Row><Field name="dID">200</Field></Row>
        </root>"""
        mock_post.return_value = _FakeResponse(200, xml)
        self.assertEqual(self._client().latest_did("W.DS"), 300)

    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_latest_did_zero_when_no_rows(self, mock_post):
        mock_post.return_value = _FakeResponse(200, "<root></root>")
        self.assertEqual(self._client().latest_did("W.DS"), 0)

    @mock.patch("tap_oracle_fusion.bicc_extract.time.sleep", return_value=None)
    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_find_file_id_found_immediately(self, mock_post, _sleep):
        xml = "<root><Row><Field name='dID'>500</Field></Row></root>"
        mock_post.return_value = _FakeResponse(200, xml)
        file_id = self._client().find_file_id("W.DS", max_attempts=3, poll_interval=0, min_did=0)
        self.assertEqual(file_id, "500")

    @mock.patch("tap_oracle_fusion.bicc_extract.time.sleep", return_value=None)
    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_find_file_id_raises_after_max_attempts(self, mock_post, _sleep):
        mock_post.return_value = _FakeResponse(200, "<root></root>")
        with self.assertRaises(ExtractError) as ctx:
            self._client().find_file_id("W.DS", max_attempts=2, poll_interval=0, min_did=0)
        self.assertIn("No new UCM file", str(ctx.exception))

    @mock.patch("tap_oracle_fusion.bicc_extract.time.sleep", return_value=None)
    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_find_file_id_waits_for_newer_file(self, mock_post, mock_sleep):
        xml_low = "<root><Row><Field name='dID'>100</Field></Row></root>"
        xml_high = "<root><Row><Field name='dID'>600</Field></Row></root>"
        mock_post.side_effect = [
            _FakeResponse(200, xml_low),
            _FakeResponse(200, xml_high),
        ]
        file_id = self._client().find_file_id(
            "W.DS", max_attempts=3, poll_interval=5, min_did=200
        )
        self.assertEqual(file_id, "600")
        mock_sleep.assert_called_once_with(5)

    @mock.patch("tap_oracle_fusion.bicc_extract.time.sleep", return_value=None)
    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_find_file_id_returns_highest_did_when_multiple_fresh(self, mock_post, _sleep):
        xml = """<root>
            <Row><Field name="dID">300</Field></Row>
            <Row><Field name="dID">500</Field></Row>
        </root>"""
        mock_post.return_value = _FakeResponse(200, xml)
        file_id = self._client().find_file_id("W.DS", max_attempts=1, poll_interval=0, min_did=200)
        self.assertEqual(file_id, "500")


# ---------------------------------------------------------------------------
# download
# ---------------------------------------------------------------------------

class TestDownload(unittest.TestCase):
    def _client(self):
        return BICCExtractClient(
            {"base_url": "https://example", "username": "u", "password": "p"}
        )

    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_raises_on_http_error(self, mock_post):
        mock_post.return_value = _FakeResponse(403, "forbidden")
        with self.assertRaises(ExtractError) as ctx:
            self._client().download("123")
        self.assertIn("GET_FILE failed", str(ctx.exception))

    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_raises_on_soap_fault(self, mock_post):
        fault = "<root><faultstring>Access denied</faultstring></root>"
        mock_post.return_value = _FakeResponse(200, fault)
        with self.assertRaises(ExtractError) as ctx:
            self._client().download("123")
        self.assertIn("SOAP fault", str(ctx.exception))

    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_returns_attachment_matched_by_cid(self, mock_post):
        zip_bytes = b"PKfakezip_content"
        xml_envelope = (
            b'<root><xop:Include xmlns:xop="http://www.w3.org/2004/08/xop/include"'
            b' href="cid:attach1"/></root>'
        )
        body, ct = _make_multipart_body([
            ({"content-type": "text/xml"}, xml_envelope),
            ({"content-type": "application/zip", "content-id": "<attach1>"}, zip_bytes),
        ])
        mock_post.return_value = _FakeResponse(200, content=body, headers={"Content-Type": ct})
        result = self._client().download("123")
        self.assertEqual(result, zip_bytes)

    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_returns_single_attachment_when_no_cid(self, mock_post):
        zip_bytes = b"PKfakezip_no_cid"
        xml_envelope = b"<root/>"
        body, ct = _make_multipart_body([
            ({"content-type": "text/xml"}, xml_envelope),
            ({"content-type": "application/zip"}, zip_bytes),
        ])
        mock_post.return_value = _FakeResponse(200, content=body, headers={"Content-Type": ct})
        result = self._client().download("123")
        self.assertEqual(result, zip_bytes)

    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_raises_when_multiple_attachments_no_cid_match(self, mock_post):
        xml_envelope = b"<root/>"
        body, ct = _make_multipart_body([
            ({"content-type": "text/xml"}, xml_envelope),
            ({"content-type": "application/zip", "content-id": "a1"}, b"data1"),
            ({"content-type": "application/zip", "content-id": "a2"}, b"data2"),
        ])
        mock_post.return_value = _FakeResponse(200, content=body, headers={"Content-Type": ct})
        with self.assertRaises(ExtractError) as ctx:
            self._client().download("123")
        self.assertIn("2 attachments", str(ctx.exception))

    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_base64_fallback(self, mock_post):
        raw = b"some binary data for base64 test"
        encoded = base64.b64encode(raw).decode()
        # Make it >= 200 chars by padding
        long_encoded = (encoded * 10)[:210]
        xml_response = f"<root>{long_encoded}</root>"
        mock_post.return_value = _FakeResponse(200, xml_response)
        result = self._client().download("123")
        self.assertIsInstance(result, bytes)

    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_no_payload_raises(self, mock_post):
        mock_post.return_value = _FakeResponse(200, "<root><tiny>x</tiny></root>")
        with self.assertRaises(ExtractError) as ctx:
            self._client().download("123")
        self.assertIn("no attachment", str(ctx.exception))

    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_invalid_xml_envelope_parse_error_is_ignored(self, mock_post):
        # ET.ParseError is swallowed; code falls through to the 'no attachment' error.
        mock_post.return_value = _FakeResponse(200, "<<< not xml >>> at all")
        with self.assertRaises(ExtractError) as ctx:
            self._client().download("123")
        self.assertIn("no attachment", str(ctx.exception))


# ---------------------------------------------------------------------------
# run_extract_to_rows
# ---------------------------------------------------------------------------

class TestRunExtractToRows(unittest.TestCase):
    def _client(self):
        return BICCExtractClient(
            {"base_url": "https://example", "username": "u", "password": "p"}
        )

    @mock.patch.object(BICCExtractClient, "download")
    @mock.patch.object(BICCExtractClient, "find_file_id", return_value="file-42")
    @mock.patch.object(BICCExtractClient, "poll", return_value="SUCCEEDED")
    @mock.patch.object(BICCExtractClient, "submit", return_value="REQ-007")
    @mock.patch.object(BICCExtractClient, "latest_did", return_value=100)
    def test_success_yields_rows(
        self, _did, _submit, _poll, _find, mock_download
    ):
        mock_download.return_value = _make_zip_bytes({"data.csv": "id,val\n1,x\n"})
        rows_iter, info = self._client().run_extract_to_rows(
            "W.DS", "job-1",
            ess_poll_interval=0,
            ucm_poll_interval=0, ucm_max_attempts=1,
        )
        rows = list(rows_iter)
        self.assertEqual(len(rows), 1)
        self.assertEqual(info["state"], "SUCCEEDED")
        self.assertEqual(info["file_id"], "file-42")
        self.assertEqual(info["request_id"], "REQ-007")
        self.assertEqual(info["ucm_did_floor"], "100")

    @mock.patch.object(BICCExtractClient, "poll", return_value="ERROR")
    @mock.patch.object(BICCExtractClient, "submit", return_value="REQ-007")
    @mock.patch.object(BICCExtractClient, "latest_did", return_value=0)
    def test_fatal_state_raises(self, _did, _submit, _poll):
        with self.assertRaises(ExtractError) as ctx:
            self._client().run_extract_to_rows(
                "W.DS", "job-1",
                ess_poll_interval=0,
                ucm_poll_interval=0, ucm_max_attempts=1,
            )
        self.assertIn("ERROR", str(ctx.exception))

    @mock.patch.object(BICCExtractClient, "poll", return_value="CANCELLED")
    @mock.patch.object(BICCExtractClient, "submit", return_value="REQ-007")
    @mock.patch.object(BICCExtractClient, "latest_did", return_value=0)
    def test_cancelled_state_raises(self, _did, _submit, _poll):
        with self.assertRaises(ExtractError):
            self._client().run_extract_to_rows(
                "W.DS", "job-1",
                ess_poll_interval=0,
                ucm_poll_interval=0, ucm_max_attempts=1,
            )


# ---------------------------------------------------------------------------
# Envelope template functions
# ---------------------------------------------------------------------------

class TestEnvelopeFunctions(unittest.TestCase):
    def test_submit_envelope_contains_datastore_and_job(self):
        env = _submit_envelope("https://ex", "user", "pass", "Worker.DS", "job-1")
        self.assertIn("Worker.DS", env)
        self.assertIn("job-1", env)

    def test_state_envelope_contains_request_id(self):
        env = _state_envelope("https://ex", "user", "pass", "REQ-001")
        self.assertIn("REQ-001", env)
        self.assertIn("getRequestState", env)

    def test_search_envelope_contains_query_text(self):
        env = _search_envelope("https://ex", "user", "pass", "dDocTitle <starts> `file_worker`")
        self.assertIn("file_worker", env)
        self.assertIn("GET_SEARCH_RESULTS", env)

    def test_get_file_envelope_contains_file_id(self):
        env = _get_file_envelope("https://ex", "user", "pass", "999")
        self.assertIn("999", env)
        self.assertIn("GET_FILE", env)

    def test_submit_envelope_escapes_xml_chars(self):
        env = _submit_envelope("https://ex", "u", "p<>&", "DS", "j")
        self.assertIn("p&lt;&gt;&amp;", env)


class TestPostNetworkErrors(unittest.TestCase):
    def _client(self):
        return BICCExtractClient(
            {"base_url": "https://example", "username": "u", "password": "p"}
        )

    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_timeout_raises_extract_error(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout("timed out")
        with self.assertRaises(ExtractError) as ctx:
            self._client().submit("DS.Worker", "job-1")
        self.assertIn("timed out", str(ctx.exception))

    @mock.patch("tap_oracle_fusion.bicc_extract.requests.post")
    def test_connection_error_raises_extract_error(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError("conn refused")
        with self.assertRaises(ExtractError) as ctx:
            self._client().submit("DS.Worker", "job-1")
        self.assertIn("connection error", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
