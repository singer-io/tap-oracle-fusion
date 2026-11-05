"""Shared SSRF-safety validation for outbound tap-oracle-fusion requests.

Oracle Fusion base_url values come straight from tap config, which may be
supplied by an untrusted or semi-trusted caller (e.g. a multi-tenant
orchestration platform). Without validation, a malicious base_url could point
the tap's HTTP/SOAP clients -- and the credentials attached to every
request -- at an arbitrary internal or attacker-controlled host (SSRF).

This module enforces that base_url:
  - uses the https scheme (no http, file, gopher, etc.)
  - does not embed credentials in the URL itself
  - contains no backslashes, which some HTTP clients (e.g. requests/urllib3)
    treat as authority/path separators even though urlparse() does not,
    letting a backslash smuggle an attacker host past the domain check below
  - has a hostname ending in one of the allowed Oracle domains below, so
    credentials can only ever be sent to genuine Oracle-operated endpoints
  - uses the default HTTPS port (443), so a validated Oracle host cannot be
    paired with an arbitrary non-standard port fronted by attacker infra

Hostname-allow-listing alone is not enough: an allow-listed hostname can
still *resolve* to a private/link-local/loopback address (misconfigured DNS,
or an attacker able to influence a later re-resolution, i.e. DNS rebinding).
`build_safe_session()` below returns a requests.Session whose HTTPS
connections validate every resolved address is public/routable and then
connect directly to that validated IP, closing the gap between the check and
the actual TCP connect.
"""
import ipaddress
import socket
import sys
from socket import timeout as SocketTimeout
from urllib.parse import urlparse

import requests
from urllib3.connection import HTTPSConnection
from urllib3.connectionpool import HTTPSConnectionPool
from urllib3.exceptions import ConnectTimeoutError, NameResolutionError, NewConnectionError
from urllib3.util import connection as urllib3_connection

# Only these Oracle-operated domains (and subdomains thereof) may receive
# tap credentials. Oracle Fusion Cloud instances are always hosted under
# *.oraclecloud.com; *.oraclepdemos.com covers Oracle's public demo/sandbox
# environments. Extend this tuple only with domains genuinely controlled by
# Oracle.
ALLOWED_BASE_URL_DOMAINS = (
    "oraclecloud.com",
    "oraclepdemos.com",
)

# Only the default HTTPS port is allowed. Oracle Fusion/BICC endpoints are
# always served on 443; accepting other ports would let an otherwise
# allow-listed hostname be repointed at a non-standard listener.
ALLOWED_BASE_URL_PORTS = (443,)


class UnsafeBaseURLError(ValueError):
    """Raised when a configured base_url is not a safe destination for outbound requests."""


def _is_allowed_domain(hostname: str) -> bool:
    hostname = hostname.lower().rstrip(".")
    return any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in ALLOWED_BASE_URL_DOMAINS
    )


def _reject_backslashes(url: str) -> None:
    # urlparse() treats a backslash as an ordinary hostname character and
    # keeps it inside netloc/hostname, so "https://host\\foo.ora
    # clecloud.com" parses with hostname ending in ".oraclecloud.com" and
    # passes the allow-list below. But requests/urllib3 (like browsers and
    # most WHATWG-based URL parsers) treat a backslash as equivalent to a
    # forward slash -- i.e. the end of the authority -- so the *actual*
    # outbound request goes to host with everything after
    # the backslash sent as the path. Rejecting any backslash up front
    # closes that host/parser disagreement entirely.
    if "\\" in url:
        raise UnsafeBaseURLError("base_url must not contain backslashes")


def assert_safe_base_url(url: str) -> str:
    """Validate that `url` is an https URL pointing at an allowed Oracle domain.

    Returns the url unchanged on success. Raises UnsafeBaseURLError otherwise.
    """
    _reject_backslashes(url)

    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise UnsafeBaseURLError(f"base_url could not be parsed: {exc}") from exc

    if parsed.scheme != "https":
        raise UnsafeBaseURLError(f"base_url must use https, got scheme={parsed.scheme!r}")

    if parsed.username or parsed.password:
        raise UnsafeBaseURLError("base_url must not contain embedded credentials")

    hostname = parsed.hostname
    if not hostname:
        raise UnsafeBaseURLError("base_url must include a hostname")

    if not _is_allowed_domain(hostname):
        raise UnsafeBaseURLError(
            f"base_url host {hostname!r} is not an allowed Oracle domain "
            f"(allowed: {', '.join(ALLOWED_BASE_URL_DOMAINS)})"
        )

    try:
        port = parsed.port
    except ValueError as exc:
        raise UnsafeBaseURLError(f"base_url has an invalid port: {exc}") from exc

    if port is not None and port not in ALLOWED_BASE_URL_PORTS:
        raise UnsafeBaseURLError(
            f"base_url port {port} is not allowed "
            f"(allowed: {', '.join(str(p) for p in ALLOWED_BASE_URL_PORTS)} or none/default)"
        )

    return url


def _is_public_ip(ip_str: str) -> bool:
    ip_obj = ipaddress.ip_address(ip_str)
    # is_private/is_reserved/etc. miss RFC 6598 shared address space
    # (100.64.0.0/10, used by carrier-grade NAT): CPython treats it as
    # neither private nor reserved, so is_global is the only property that
    # correctly excludes it. is_global doesn't exclude multicast, so that
    # is checked separately.
    return ip_obj.is_global and not ip_obj.is_multicast


def _resolve_to_public_ip(host: str, port: int) -> str:
    """Resolve `host`, require every candidate address to be public/routable,
    and return the first one so the caller can connect directly to it."""
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not infos:
        raise socket.gaierror(f"no addresses found for host {host!r}")

    resolved_ips = {sockaddr[0] for *_rest, sockaddr in infos}
    for ip_str in resolved_ips:
        if not _is_public_ip(ip_str):
            raise UnsafeBaseURLError(
                f"host {host!r} resolved to non-public address {ip_str!r}; refusing to connect"
            )
    return infos[0][4][0]


class _PinnedHTTPSConnection(HTTPSConnection):
    """HTTPSConnection that validates the resolved address is public and then
    connects directly to it, so a later DNS answer (rebinding) can never be
    substituted between the check and the actual TCP connect. TLS SNI/
    certificate hostname verification still uses self.host, unaffected by
    which IP the underlying socket is connected to.
    """

    def _new_conn(self) -> socket.socket:
        try:
            validated_ip = _resolve_to_public_ip(self.host, self.port)
        except socket.gaierror as exc:
            raise NameResolutionError(self.host, self, exc) from exc

        try:
            sock = urllib3_connection.create_connection(
                (validated_ip, self.port),
                self.timeout,
                source_address=self.source_address,
                socket_options=self.socket_options,
            )
        except SocketTimeout as exc:
            raise ConnectTimeoutError(
                self,
                f"Connection to {self.host} timed out. (connect timeout={self.timeout})",
            ) from exc
        except OSError as exc:
            raise NewConnectionError(
                self, f"Failed to establish a new connection: {exc}"
            ) from exc

        sys.audit("http.client.connect", self, self.host, self.port)
        return sock


class _PinnedHTTPSConnectionPool(HTTPSConnectionPool):
    ConnectionCls = _PinnedHTTPSConnection


class _SafeHTTPAdapter(requests.adapters.HTTPAdapter):
    """Transport adapter whose HTTPS connections are pinned to a validated,
    public resolved IP (see _PinnedHTTPSConnection)."""

    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = dict(
            self.poolmanager.pool_classes_by_scheme,
            https=_PinnedHTTPSConnectionPool,
        )


def build_safe_session() -> requests.Session:
    """Return a requests.Session whose https:// requests refuse to connect if
    the hostname resolves to a private/loopback/link-local/reserved address.
    """
    session = requests.Session()
    session.mount("https://", _SafeHTTPAdapter())
    return session
