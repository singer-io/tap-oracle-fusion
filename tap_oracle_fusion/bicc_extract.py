"""BICC extract client for Oracle Fusion ESS/UCM job submission and file retrieval."""
import base64
import csv
import hashlib
import io
import json
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, Mapping, Optional, Tuple
from urllib.parse import unquote
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from zipfile import BadZipFile, ZipFile

import requests
import singer

LOGGER = singer.get_logger()

ESS_PATH = "bi/ess/esswebservice"
UCM_PATH = "idcws/GenericSoapPort"
JOBS_PATH = "biacm/rest/meta/jobs"
DEFAULT_INITIAL_EXTRACT_DATE = "2000-01-01T00:00:00.000"
TERMINAL_STATES = {"SUCCEEDED", "WARNING", "ERROR", "CANCELLED"}
FATAL_STATES = {"ERROR", "CANCELLED"}


def _set_csv_field_size_limit() -> None:
    limit = sys.maxsize
    while limit > 0:
        try:
            csv.field_size_limit(limit)
            return
        except OverflowError:
            limit //= 10


_set_csv_field_size_limit()


class ExtractError(Exception):
    """Raised when job creation or ESS/UCM extraction fails."""


class BICCExtractClient:
    """Client that submits ESS jobs and retrieves BICC extract files via UCM."""

    def __init__(self, config: Mapping[str, Any]) -> None:
        """Initialise from tap config."""
        self.base_url = str(config.get("base_url", "")).rstrip("/")
        self.username = str(config.get("username", ""))
        self.password = str(config.get("password", ""))
        self.timeout = float(config.get("request_timeout", 300))
        self.ess_url = f"{self.base_url}/{ESS_PATH}"
        self.ucm_url = f"{self.base_url}/{UCM_PATH}"

    @staticmethod
    def datastore_slug(datastore: str) -> str:
        """Return a filesystem-safe slug for a datastore name."""
        return datastore.strip().lower().replace(".", "_")

    def create_bicc_job(
        self,
        datastore: str,
        initial_extract_date: str,
        job_name: Optional[str] = None,
    ) -> str:
        """Create or reuse a BICC extract job and return its job ID."""
        name = job_name or f"file_{self.datastore_slug(datastore)}"
        # Oracle BICC requires yyyy-MM-ddT00:00:00.000 — strip any existing time/tz then re-attach
        date_part = initial_extract_date.replace("Z", "").replace("+00:00", "").split("T")[0]
        normalized_date = f"{date_part}T00:00:00.000"
        job = {
            "name": name,
            "description": f"{datastore} extract (tap-oracle-fusion)",
            "dataStores": [
                {
                    "dataStoreMeta": {
                        "dataStoreKey": datastore,
                        "initialExtractDate": normalized_date,
                    },
                    "groupNumber": 1,
                    "groupItemPriority": 1,
                }
            ],
        }
        try:
            response = requests.put(
                f"{self.base_url}/{JOBS_PATH}",
                json=job,
                auth=(self.username, self.password),
                headers={"Accept": "application/json"},
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as exc:
            raise ExtractError(
                f"create-job timed out after {self.timeout}s: {exc}"
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise ExtractError(
                f"create-job connection error: {exc}"
            ) from exc
        try:
            body = response.json()
        except ValueError:
            body = None
        if response.status_code >= 400 or not isinstance(body, dict):
            raise ExtractError(
                f"create-job failed status={response.status_code} body={response.text[:400]}"
            )
        if not str(body.get("status", "")).upper().startswith("SUCCESS"):
            raise ExtractError(f"create-job returned non-success: {json.dumps(body)[:400]}")
        job_id = str(body.get("id", "")).strip()
        if not job_id:
            raise ExtractError(f"create-job response missing id: {json.dumps(body)[:400]}")
        LOGGER.info("Created/reused BICC job name=%s id=%s datastore=%s", name, job_id, datastore)
        return job_id

    def run_extract_to_rows(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        datastore: str,
        job_id: str,
        ess_poll_interval: int,
        ucm_poll_interval: int,
        ucm_max_attempts: int,
    ) -> Tuple[Iterator[Dict[str, str]], Dict[str, str]]:
        """Submit an ESS extract job and yield CSV rows from the resulting UCM file."""
        pre_did = self.latest_did(datastore)
        request_id = self.submit(datastore, job_id)
        LOGGER.info(
            "Submitted ESS request_id=%s job_id=%s datastore=%s ucm_did_floor=%s",
            request_id,
            job_id,
            datastore,
            pre_did,
        )
        state = self.poll(request_id, ess_poll_interval)
        if state in FATAL_STATES:
            raise ExtractError(f"ESS terminal state={state} request_id={request_id}")

        file_id = self.find_file_id(
            datastore,
            max_attempts=ucm_max_attempts,
            poll_interval=ucm_poll_interval,
            min_did=pre_did,
        )
        payload = self.download(file_id)
        return _iter_csv_rows_from_zip_bytes(payload), {
            "request_id": request_id,
            "state": state,
            "file_id": file_id,
            "ucm_did_floor": str(pre_did),
        }

    def _post(self, url: str, envelope: str) -> requests.Response:
        """Send a SOAP/XML POST request and return the raw response."""
        try:
            return requests.post(
                url,
                data=envelope.encode("utf-8"),
                headers={"Content-Type": "text/xml; charset=utf-8"},
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as exc:
            raise ExtractError(
                f"SOAP request timed out after {self.timeout}s to {url}: {exc}"
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise ExtractError(
                f"SOAP request connection error to {url}: {exc}"
            ) from exc

    def submit(self, datastore: str, job_id: str) -> str:
        """Submit an ESS extract request and return the ESS request ID."""
        resp = self._post(
            self.ess_url,
            _submit_envelope(
                self.base_url, self.username, self.password, datastore, job_id
            ),
        )
        request_id = _submit_request_id(resp.text)
        if not request_id:
            fault = _text_by_local_name(resp.text, "faultstring")
            raise ExtractError(
                f"submitRequest missing requestId. "
                f"status={resp.status_code} fault={fault or 'none'}"
            )
        return request_id

    def poll(self, request_id: str, poll_interval: int) -> str:
        """Poll ESS until a terminal state is reached and return the final state."""
        state: Optional[str] = None
        attempt = 0
        while state not in TERMINAL_STATES:
            attempt += 1
            resp = self._post(
                self.ess_url,
                _state_envelope(self.base_url, self.username, self.password, request_id),
            )
            state = _text_by_local_name(resp.text, "state")
            if not state:
                fault = _text_by_local_name(resp.text, "faultstring")
                raise ExtractError(f"getRequestState missing state. fault={fault or 'none'}")
            LOGGER.info("ESS poll attempt=%s state=%s", attempt, state)
            if state not in TERMINAL_STATES:
                time.sleep(max(1, poll_interval))

        return state

    def _search_datastore_files(self, datastore: str) -> list[dict[str, str]]:
        """Search UCM for extract files belonging to a datastore and return row dicts."""
        query_text = f"dDocTitle <starts> `file_{self.datastore_slug(datastore)}`"
        resp = self._post(
            self.ucm_url,
            _search_envelope(self.base_url, self.username, self.password, query_text),
        )
        envelope, _ = _envelope_and_attachments(resp)
        try:
            root = ET.fromstring(envelope)
        except ET.ParseError as err:
            raise ExtractError(
                f"UCM search returned unparseable response (http {resp.status_code}): {err}"
            ) from err
        fault = _soap_fault(root)
        if fault:
            raise ExtractError(f"UCM search SOAP fault: {fault}")
        status = _document_field(root, "StatusCode")
        if status not in (None, "", "0"):
            raise ExtractError(
                f"UCM search error StatusCode={status} "
                f"StatusMessage={_document_field(root, 'StatusMessage')}"
            )
        return _search_rows(root)

    def latest_did(self, datastore: str) -> int:
        """Return the highest UCM dID seen for a datastore, or 0 if none found."""
        dids = [_as_int(r.get("dID")) for r in self._search_datastore_files(datastore)]
        return max((d for d in dids if d is not None), default=0)

    def find_file_id(
        self, datastore: str, max_attempts: int, poll_interval: int, min_did: int = 0
    ) -> str:
        """Poll UCM until a new extract file appears above min_did and return its dID."""
        for attempt in range(1, max(max_attempts, 1) + 1):
            rows = self._search_datastore_files(datastore)
            fresh = sorted(
                (r for r in rows if (_as_int(r.get("dID")) or 0) > min_did),
                key=lambda r: _as_int(r.get("dID")) or 0,
                reverse=True,
            )
            LOGGER.info(
                "UCM search attempt=%s rows=%s fresh_above_%s=%s",
                attempt,
                len(rows),
                min_did,
                len(fresh),
            )
            if fresh:
                return str(fresh[0]["dID"])
            if attempt < max_attempts:
                time.sleep(max(1, poll_interval))
        raise ExtractError(
            f"No new UCM file for {datastore} after {max_attempts} attempts"
        )

    def download(self, file_id: str) -> bytes:
        """Download a UCM file by its dID and return the raw bytes."""
        resp = self._post(
            self.ucm_url,
            _get_file_envelope(self.base_url, self.username, self.password, file_id),
        )
        if resp.status_code >= 400:
            raise ExtractError(f"UCM GET_FILE failed with status {resp.status_code}")

        envelope, attachments = _envelope_and_attachments(resp)
        try:
            fault = _soap_fault(ET.fromstring(envelope))
            if fault:
                raise ExtractError(f"UCM GET_FILE SOAP fault: {fault}")
        except ET.ParseError:
            pass

        cid_match = re.search(rb'href="cid:([^"]+)"', envelope)
        if cid_match and attachments:
            cid = unquote(cid_match.group(1).decode("latin1"))
            for headers, body in attachments:
                if headers.get("content-id", "").strip("<>") == cid:
                    return body
        if len(attachments) == 1:
            return attachments[0][1]
        if attachments:
            raise ExtractError(
                f"GET_FILE returned {len(attachments)} attachments, none matched the xop cid"
            )

        blob = re.search(rb">([A-Za-z0-9+/=\r\n]{200,})<", envelope)
        if blob:
            return base64.b64decode(re.sub(rb"\s+", b"", blob.group(1)))
        raise ExtractError("GET_FILE response had no attachment or decodable payload")


def _iter_csv_rows_from_zip_bytes(payload: bytes) -> Iterator[Dict[str, str]]:
    """Yield CSV row dicts from a ZIP payload held in memory.

    Memory-efficient: streams each CSV entry row-by-row via TextIOWrapper instead
    of decoding the full file into a string, and deduplicates across CSV files
    using a compact SHA-256 hash set (32 bytes/entry) rather than storing full
    row tuples.
    """
    try:
        with ZipFile(io.BytesIO(payload), "r") as archive:
            members = archive.namelist()
            csv_names = [m for m in members if m.lower().endswith(".csv")] or members[:1]
            # Oracle BICC can package both a full (seed) and an incremental (delta)
            # extract in the same ZIP.  Deduplicate across all CSV files so that
            # records appearing in more than one file are only yielded once.
            # Store a SHA-256 digest (32 bytes) per row instead of the full row
            # tuple to keep the seen-set memory footprint small.
            seen: set = set()
            for csv_name in csv_names:
                with archive.open(csv_name) as raw_fh:
                    text_fh = io.TextIOWrapper(raw_fh, encoding="utf-8-sig", errors="replace")
                    for row in csv.DictReader(text_fh):
                        row_dict = {k: (v if v is not None else "") for k, v in row.items()}
                        row_key = hashlib.sha256(
                            repr(sorted(row_dict.items())).encode()
                        ).digest()
                        if row_key in seen:
                            continue
                        seen.add(row_key)
                        yield row_dict
    except BadZipFile as err:
        raise ExtractError(f"UCM payload is not a valid zip: {err}") from err


def _split_multipart(
    content: bytes, content_type: str
) -> Optional[list[tuple[dict[str, str], bytes]]]:
    match = re.search(r'boundary="?([^";]+)"?', content_type or "")
    if not match:
        return None
    boundary = ("--" + match.group(1)).encode()
    parts: list[tuple[dict[str, str], bytes]] = []
    mv = memoryview(content)

    # Locate all boundary positions without splitting the buffer — this avoids
    # creating multiple byte copies of the large binary payload (ZIP attachment).
    # Each body is extracted as a single exact-size allocation via bytes(mv[s:e])
    # rather than as a by-product of bytes.split() which clones every section.
    pos = 0
    boundary_positions: list[int] = []
    while True:
        idx = content.find(boundary, pos)
        if idx == -1:
            break
        boundary_positions.append(idx)
        pos = idx + 1

    for i in range(len(boundary_positions) - 1):
        part_start = boundary_positions[i] + len(boundary)
        if content[part_start:part_start + 2] == b"\r\n":
            part_start += 2
        if content[part_start:part_start + 2] == b"--":
            break  # final boundary marker ("--boundary--")

        part_end = boundary_positions[i + 1]
        if content[part_end - 2:part_end] == b"\r\n":
            part_end -= 2

        header_end = content.find(b"\r\n\r\n", part_start)
        if header_end == -1 or header_end >= part_end:
            continue

        headers: dict[str, str] = {}
        for line in bytes(mv[part_start:header_end]).decode("latin1").split("\r\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                headers[key.strip().lower()] = val.strip()

        body_start = header_end + 4
        parts.append((headers, bytes(mv[body_start:part_end])))

    return parts


def _envelope_and_attachments(
    response: requests.Response,
) -> tuple[bytes, list[tuple[dict[str, str], bytes]]]:
    content_type = response.headers.get("Content-Type", "")
    parts = _split_multipart(response.content, content_type)
    if not parts:
        return response.content, []

    root_idx = 0
    start = re.search(r'start="?<?([^">;]+)>?"?', content_type)
    if start:
        start_id = start.group(1)
        for i, (headers, _body) in enumerate(parts):
            if headers.get("content-id", "").strip("<>") == start_id:
                root_idx = i
                break

    root = parts[root_idx][1]
    attachments = [p for i, p in enumerate(parts) if i != root_idx]
    return root, attachments


def _local(tag: str) -> str:
    return tag.split("}")[-1]


def _document_field(root: ET.Element, field_name: str) -> Optional[str]:
    for element in root.iter():
        if _local(element.tag) == "Field":
            name = element.attrib.get("name") or element.attrib.get("Name")
            if name == field_name:
                return (element.text or "").strip()
    return None


def _soap_fault(root: ET.Element) -> Optional[str]:
    for element in root.iter():
        if _local(element.tag) == "faultstring" and (element.text or "").strip():
            return element.text.strip()
    return None


def _search_rows(root: ET.Element) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in root.iter():
        if _local(row.tag) != "Row":
            continue
        item: dict[str, str] = {}
        for field in row:
            if _local(field.tag) != "Field":
                continue
            name = field.attrib.get("name") or field.attrib.get("Name")
            value = (field.text or "").strip()
            if name and value:
                item[name] = value
        if "dID" in item:
            rows.append(item)
    return rows


def _as_int(value: Optional[str]) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_plus_seconds_iso(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text_by_local_name(xml_text: str, local_name: str) -> Optional[str]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    for element in root.iter():
        if _local(element.tag) == local_name and (element.text or "").strip():
            return element.text.strip()
    return None


def _submit_request_id(xml_text: str) -> Optional[str]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    for element in root.iter():
        if _local(element.tag) != "requestId":
            continue
        for child in list(element):
            if _local(child.tag) == "value" and (child.text or "").strip():
                return child.text.strip()
        if (element.text or "").strip():
            return element.text.strip()
    return None


# pylint: disable=line-too-long
def _soap_header(action_url: str, username: str, password: str) -> str:
    created = _utc_now_iso()
    expires = _utc_plus_seconds_iso(120)
    return f"""
  <soapenv:Header>
    <wsa:MessageID>uuid:{uuid.uuid4()}</wsa:MessageID>
    <wsa:Action>{action_url}</wsa:Action>
    <wsse:Security soapenv:mustUnderstand=\"1\"
      xmlns:wsse=\"http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd\"
      xmlns:wsu=\"http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd\">
      <wsu:Timestamp><wsu:Created>{created}</wsu:Created><wsu:Expires>{expires}</wsu:Expires></wsu:Timestamp>
      <wsse:UsernameToken>
        <wsse:Username>{escape(username)}</wsse:Username>
        <wsse:Password Type=\"http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText\">{escape(password)}</wsse:Password>
        <wsu:Created>{created}</wsu:Created>
      </wsse:UsernameToken>
    </wsse:Security>
  </soapenv:Header>
"""


def _submit_envelope(base_url: str, username: str, password: str, datastore: str, job_id: str) -> str:
    return f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<soapenv:Envelope xmlns:soapenv=\"http://schemas.xmlsoap.org/soap/envelope/\"
                  xmlns:sch=\"http://xmlns.oracle.com/scheduler\"
                  xmlns:typ=\"http://xmlns.oracle.com/scheduler/types\"
                  xmlns:wsa=\"http://schemas.xmlsoap.org/ws/2004/08/addressing\"
                  xmlns:wsse=\"http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd\"
                  xmlns:wsu=\"http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd\">
{_soap_header(f"{base_url}/{ESS_PATH}", username, password)}
  <soapenv:Body>
    <sch:submitRequest>
      <sch:description>{escape(datastore)} export</sch:description>
      <sch:jobDefinitionId>
        <typ:name>BICloudConnectorJobDefinition</typ:name>
        <typ:packageName>oracle.apps.ess.biccc</typ:packageName>
        <typ:type>JOB_DEFINITION</typ:type>
      </sch:jobDefinitionId>
      <sch:application>oracle.biacm</sch:application>
      <sch:requestedStartTime/>
      <sch:requestParameters>
        <typ:parameter><typ:dataType>STRING</typ:dataType><typ:name>SYS_className</typ:name><typ:value>oracle.esshost.impl.CloudAdaptorJobImpl</typ:value></typ:parameter>
        <typ:parameter><typ:dataType>STRING</typ:dataType><typ:name>SYS_application</typ:name><typ:value>BI Cloud Adaptor</typ:value></typ:parameter>
        <typ:parameter><typ:dataType>STRING</typ:dataType><typ:name>SYS_requestCategory</typ:name><typ:value>JobSchedule</typ:value></typ:parameter>
        <typ:parameter><typ:dataType>STRING</typ:dataType><typ:name>EXTRACT_JOB_TYPE</typ:name><typ:value>VO_EXTRACT</typ:value></typ:parameter>
        <typ:parameter><typ:dataType>STRING</typ:dataType><typ:name>DATA_STORE_LIST</typ:name><typ:value>{escape(datastore)}</typ:value></typ:parameter>
        <typ:parameter><typ:dataType>LONG</typ:dataType><typ:name>JOB_ID</typ:name><typ:value>{job_id}</typ:value></typ:parameter>
      </sch:requestParameters>
    </sch:submitRequest>
  </soapenv:Body>
</soapenv:Envelope>
"""


def _state_envelope(base_url: str, username: str, password: str, request_id: str) -> str:
    return f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<soapenv:Envelope xmlns:soapenv=\"http://schemas.xmlsoap.org/soap/envelope/\"
                  xmlns:sch=\"http://xmlns.oracle.com/scheduler\"
                  xmlns:wsa=\"http://schemas.xmlsoap.org/ws/2004/08/addressing\"
                  xmlns:wsse=\"http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd\"
                  xmlns:wsu=\"http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd\">
{_soap_header(f"{base_url}/{ESS_PATH}", username, password)}
  <soapenv:Body><sch:getRequestState><sch:requestId>{request_id}</sch:requestId></sch:getRequestState></soapenv:Body>
</soapenv:Envelope>
"""


def _search_envelope(base_url: str, username: str, password: str, query_text: str, result_count: int = 50) -> str:
    return f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<soapenv:Envelope xmlns:soapenv=\"http://schemas.xmlsoap.org/soap/envelope/\"
                  xmlns:wsa=\"http://schemas.xmlsoap.org/ws/2004/08/addressing\"
                  xmlns:ucm=\"http://www.oracle.com/UCM\">
{_soap_header(f"{base_url}/{UCM_PATH}", username, password)}
  <soapenv:Body>
    <ucm:GenericRequest webKey='cs'>
      <ucm:Service IdcService='GET_SEARCH_RESULTS'>
        <ucm:Document>
          <ucm:Field name='QueryText'>{escape(query_text)}</ucm:Field>
          <ucm:Field name='ResultCount'>{max(result_count, 20)}</ucm:Field>
          <ucm:Field name='SortField'>dInDate</ucm:Field>
          <ucm:Field name='SortOrder'>Desc</ucm:Field>
        </ucm:Document>
      </ucm:Service>
    </ucm:GenericRequest>
  </soapenv:Body>
</soapenv:Envelope>
"""


def _get_file_envelope(base_url: str, username: str, password: str, file_id: str) -> str:
    return f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<soapenv:Envelope xmlns:soapenv=\"http://schemas.xmlsoap.org/soap/envelope/\"
                  xmlns:wsa=\"http://schemas.xmlsoap.org/ws/2004/08/addressing\"
                  xmlns:ucm=\"http://www.oracle.com/UCM\"
                  xmlns:wsse=\"http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd\"
                  xmlns:wsu=\"http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd\">
{_soap_header(f"{base_url}/{UCM_PATH}", username, password)}
  <soapenv:Body>
    <ucm:GenericRequest webKey='cs'>
      <ucm:Service IdcService='GET_FILE'>
        <ucm:Document><ucm:Field name='dID'>{file_id}</ucm:Field></ucm:Document>
      </ucm:Service>
    </ucm:GenericRequest>
  </soapenv:Body>
</soapenv:Envelope>
"""
