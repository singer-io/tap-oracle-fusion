from typing import Any, Dict, Mapping, Optional, Tuple
from datetime import datetime, timedelta

import backoff, time
import requests
from requests import session
from requests.exceptions import Timeout, ConnectionError, ChunkedEncodingError
from singer import get_logger, metrics

from tap_oracle_fusion.exceptions import ERROR_CODE_EXCEPTION_MAPPING, OracleFusionError, OracleFusionBackoffError

LOGGER = get_logger()
REQUEST_TIMEOUT = 300
ACCESS_URL = "https://{server}.identity.oraclecloud.com/oauth2/v1/token"

def raise_for_error(response: requests.Response) -> None:
    """Raises the associated response exception. Takes in a response object,
    checks the status code, and throws the associated exception based on the
    status code.

    :param resp: requests.Response object
    """
    try:
        response_json = response.json()
    except Exception:
        response_json = {}
    if response.status_code not in [200, 201, 204]:
        if response_json.get("error"):
            message = f"HTTP-error-code: {response.status_code}, Error: {response_json.get('error')}"
        else:
            error_message = ERROR_CODE_EXCEPTION_MAPPING.get(
                response.status_code, {}
            ).get("message", "Unknown Error")
            message = f"HTTP-error-code: {response.status_code}, Error: {response_json.get('message', error_message)}"
        exc = ERROR_CODE_EXCEPTION_MAPPING.get(response.status_code, {}).get(
            "raise_exception", OracleFusionError
        )
        raise exc(message, response) from None
    
def wait_if_retry_after(details):
    """Backoff handler that checks for a 'retry_after' attribute in the exception
    and sleeps for the specified duration to respect API rate limits.
    """
    exc = details['exception']
    if hasattr(exc, 'retry_after') and exc.retry_after is not None:
        time.sleep(exc.retry_after)  # Force exact wait


class Client:
    """
    A Wrapper class.
    ~~~
    Performs:
     - Authentication
     - Response parsing
     - HTTP Error handling and retry
    """

    def __init__(self, config: Mapping[str, Any]) -> None:
        self.config = config
        self._session = session()
        self.instance = config.get("instance")
        self.region = config.get("region")
        self.base_url = "https://{self.instance}.fa.{self.region}.oraclecloud.com"
        config_request_timeout = config.get("request_timeout")
        self.request_timeout = float(config_request_timeout) if config_request_timeout else REQUEST_TIMEOUT

    def __enter__(self):
        self._get_access_token()
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self._session.close()

    def _get_access_token(self) -> None:
        """Fetches a new oracle fusion token using client credentials flow."""
        LOGGER.info("Requesting new access token from Microsoft Graph")

        token_url = ACCESS_URL.format(self.config["server"])

        resp_json = self.make_request(
            method="POST",
            endpoint=token_url,
            headers={
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body={
                "client_id": self.config["client_id"],
                "client_secret": self.config["client_secret"],
                "scope": self.config["scope"],
                "grant_type": self.config["grant_type"]
            },
            is_auth_req=False
        )

        self._access_token = resp_json["access_token"]
        expires_in_seconds = int(resp_json.get("expires_in", 3600))
        self._expires_at = datetime.now() + timedelta(seconds=expires_in_seconds)

        LOGGER.info("Received new access token, valid for %s seconds", expires_in_seconds)


    def authenticate(self, headers: Dict, params: Dict) -> Tuple[Dict, Dict]:
        """Authenticates the request with the token, refreshing it if expired."""
        if datetime.now() >= self._expires_at:
            LOGGER.info("Access token expired. Refreshing...")
            self._get_access_token()
        headers["Authorization"] = self._access_token
        return headers, params
    
    def get(self, endpoint: str, params: Dict, headers: Dict, path: str = None) -> Any:
        """Calls the make_request method with a prefixed method type `GET`"""
        endpoint = endpoint or f"{self.base_url}/{path}"
        headers, params = self.authenticate(headers, params)
        return self.__make_request("GET", endpoint, headers=headers, params=params, timeout=self.request_timeout)


    def make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        path: Optional[str] = None
    ) -> Any:
        """
        Sends an HTTP request to the specified API endpoint.
        """
        params = params or {}
        headers = headers or {}
        body = body or {}
        endpoint = endpoint or f"{self.base_url}/{path}"
        headers, params = self.authenticate(headers, params)
        return self.__make_request(
            method, endpoint,
            headers=headers,
            params=params,
            data=body,
            timeout=self.request_timeout
        )

    @backoff.on_exception(
        wait_gen=lambda: backoff.expo(factor=2),
        on_backoff=wait_if_retry_after,
        exception=(
            ConnectionResetError,
            ConnectionError,
            ChunkedEncodingError,
            Timeout,
            OracleFusionBackoffError
        ),
        max_tries=5,
    )
    def __make_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Optional[Mapping[Any, Any]]:
        """Performs HTTP Operations."""
        method = method.upper()
        with metrics.http_request_timer(endpoint):
            if method in ("GET", "POST"):
                if method == "GET":
                    kwargs.pop("data", None)
                response = self._session.request(method, endpoint, **kwargs)
                raise_for_error(response)
            else:
                raise ValueError(f"Unsupported method: {method}")

        return response.json()

