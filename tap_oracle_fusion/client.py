from typing import Any, Dict, Iterator, Mapping, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import backoff
import requests
import singer

LOGGER = singer.get_logger()
REQUEST_TIMEOUT = 300


class OracleClientError(Exception):
    """Raised for Oracle API errors."""


class OracleClient:
    """HTTP client wrapper with retries and pagination helpers."""

    def __init__(self, config: Mapping[str, Any]) -> None:
        self.config = config
        self.session = requests.Session()
        self.base_url = self._resolve_base_url(config)
        self.request_timeout = float(config.get("request_timeout", REQUEST_TIMEOUT))

    @staticmethod
    def _resolve_base_url(config: Mapping[str, Any]) -> str:
        if config.get("base_url"):
            return str(config["base_url"]).rstrip("/")

        server = str(config.get("server", "")).strip()
        region = str(config.get("region", "")).strip()
        instance = str(config.get("instance", "")).strip()

        if instance and region:
            return f"https://{instance}.fa.{region}.oraclecloud.com"

        if server.startswith("http://") or server.startswith("https://"):
            return server.rstrip("/")

        if server and region:
            return f"https://{server}.fa.{region}.oraclecloud.com"

        if server:
            return f"https://{server}"

        raise OracleClientError(
            "Unable to resolve Oracle base URL. Provide base_url or server/region."
        )

    def _auth_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/vnd.oracle.adf.resourceitem+json",
        }

        if self.config.get("access_token"):
            headers["Authorization"] = f"Bearer {self.config['access_token']}"

        return headers

    def _auth_tuple(self) -> Optional[Tuple[str, str]]:
        username = self.config.get("username")
        password = self.config.get("password")
        if username and password:
            return (str(username), str(password))
        return None

    @staticmethod
    def _extract_retry_after_seconds(response: Optional[requests.Response]) -> int:
        if response is None:
            return 60
        try:
            return int(response.headers.get("Retry-After", 60))
        except (TypeError, ValueError):
            return 60

    @staticmethod
    def _wait_if_retry_after(details: Mapping[str, Any]) -> None:
        exc = details["exception"]
        retry_after = getattr(exc, "retry_after", None)
        if retry_after:
            LOGGER.warning("Rate limited. Waiting %s seconds before retry", retry_after)
            singer.utils.sleep(retry_after)

    @staticmethod
    def _raise_for_http_error(response: requests.Response) -> None:
        if response.status_code in (200, 201, 204):
            return

        if response.status_code == 429:
            err = OracleClientError("Rate limit exceeded")
            setattr(err, "retry_after", OracleClient._extract_retry_after_seconds(response))
            raise err

        if 500 <= response.status_code < 600:
            raise OracleClientError(
                f"Server error {response.status_code}: {response.text[:500]}"
            )

        raise OracleClientError(
            f"HTTP {response.status_code}: {response.text[:500]}"
        )

    @backoff.on_exception(
        backoff.expo,
        (requests.exceptions.Timeout, requests.exceptions.ConnectionError, OracleClientError),
        max_tries=5,
        on_backoff=_wait_if_retry_after,
    )
    def get(self, path: str, params: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        LOGGER.info("Oracle request: %s params=%s", url, params or {})

        response = self.session.get(
            url,
            params=params,
            headers=self._auth_headers(),
            auth=self._auth_tuple(),
            timeout=self.request_timeout,
        )
        self._raise_for_http_error(response)

        payload = response.json()
        if not isinstance(payload, dict):
            raise OracleClientError("Expected JSON object response")
        return payload

    @staticmethod
    def _extract_records(payload: Mapping[str, Any]) -> list:
        for key in ("items", "data"):
            records = payload.get(key)
            if isinstance(records, list):
                return records
        return []

    @staticmethod
    def _parse_next_link(payload: Mapping[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
        links = payload.get("links")
        if not isinstance(links, list):
            return None

        for link in links:
            if not isinstance(link, Mapping):
                continue
            if str(link.get("rel", "")).lower() != "next":
                continue

            href = link.get("href")
            if not isinstance(href, str) or not href:
                continue

            parsed = urlparse(href)
            path = parsed.path.lstrip("/")
            query_dict = {k: v[-1] for k, v in parse_qs(parsed.query).items() if v}
            return path, query_dict

        return None

    def get_records(self, path: str, params: Optional[Mapping[str, Any]] = None) -> Iterator[Dict[str, Any]]:
        """Yield records from a collection endpoint using common Oracle pagination styles."""
        page_size = int(self.config.get("page_size", 100))
        current_path = path
        current_params = dict(params or {})
        current_params.setdefault("limit", page_size)
        current_params.setdefault("offset", 0)

        while True:
            payload = self.get(current_path, params=current_params)
            records = self._extract_records(payload)
            for record in records:
                if isinstance(record, dict):
                    yield record

            next_link = self._parse_next_link(payload)
            if next_link:
                current_path, current_params = next_link
                continue

            has_more = payload.get("hasMore")
            if isinstance(has_more, bool) and has_more:
                next_offset = int(current_params.get("offset", 0)) + int(current_params.get("limit", page_size))
                current_params["offset"] = next_offset
                continue

            break
