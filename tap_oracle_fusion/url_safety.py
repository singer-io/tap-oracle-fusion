"""Shared SSRF-safety validation for outbound tap-oracle-fusion requests.

Oracle Fusion base_url values come straight from tap config, which may be
supplied by an untrusted or semi-trusted caller (e.g. a multi-tenant
orchestration platform). Without validation, a malicious base_url could point
the tap's HTTP/SOAP clients -- and the credentials attached to every
request -- at an arbitrary internal or attacker-controlled host (SSRF).

This module enforces that base_url:
  - uses the https scheme (no http, file, gopher, etc.)
  - does not embed credentials in the URL itself
  - has a hostname ending in one of the allowed Oracle domains below, so
    credentials can only ever be sent to genuine Oracle-operated endpoints
"""
from urllib.parse import urlparse

# Only these Oracle-operated domains (and subdomains thereof) may receive
# tap credentials. Oracle Fusion Cloud instances are always hosted under
# *.oraclecloud.com; *.oraclepdemos.com covers Oracle's public demo/sandbox
# environments. Extend this tuple only with domains genuinely controlled by
# Oracle.
ALLOWED_BASE_URL_DOMAINS = (
    "oraclecloud.com",
    "oraclepdemos.com",
)


class UnsafeBaseURLError(ValueError):
    """Raised when a configured base_url is not a safe destination for outbound requests."""


def _is_allowed_domain(hostname: str) -> bool:
    hostname = hostname.lower().rstrip(".")
    return any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in ALLOWED_BASE_URL_DOMAINS
    )


def assert_safe_base_url(url: str) -> str:
    """Validate that `url` is an https URL pointing at an allowed Oracle domain.

    Returns the url unchanged on success. Raises UnsafeBaseURLError otherwise.
    """
    parsed = urlparse(url)

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

    return url

