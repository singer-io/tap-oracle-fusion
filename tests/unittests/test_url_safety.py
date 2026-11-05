"""Tests for tap_oracle_fusion.url_safety SSRF guard."""
import socket
import unittest
from unittest.mock import patch

from tap_oracle_fusion.url_safety import (
    assert_safe_base_url,
    build_safe_session,
    UnsafeBaseURLError,
    _is_public_ip,
    _resolve_to_public_ip,
)


class TestAssertSafeBaseUrl(unittest.TestCase):
    def test_allows_oraclecloud_domain(self):
        self.assertEqual(
            assert_safe_base_url("https://my-instance.oraclecloud.com"),
            "https://my-instance.oraclecloud.com",
        )

    def test_allows_oraclepdemos_domain(self):
        self.assertEqual(
            assert_safe_base_url("https://example.oraclepdemos.com"),
            "https://example.oraclepdemos.com",
        )

    def test_rejects_oracle_dot_com(self):
        # oracle.com was intentionally dropped from the allow-list.
        with self.assertRaises(UnsafeBaseURLError):
            assert_safe_base_url("https://example.oracle.com")

    def test_rejects_http_scheme(self):
        with self.assertRaises(UnsafeBaseURLError):
            assert_safe_base_url("http://my-instance.oraclecloud.com")

    def test_rejects_non_http_scheme(self):
        with self.assertRaises(UnsafeBaseURLError):
            assert_safe_base_url("file:///etc/passwd")

    def test_rejects_embedded_credentials(self):
        with self.assertRaises(UnsafeBaseURLError):
            assert_safe_base_url("https://user:pass@my-instance.oraclecloud.com")

    def test_rejects_missing_hostname(self):
        with self.assertRaises(UnsafeBaseURLError):
            assert_safe_base_url("https://")

    def test_rejects_malformed_ipv6_authority(self):
        # urlparse() itself raises ValueError for an unmatched IPv6 bracket;
        # that must be normalized to UnsafeBaseURLError, not leak out raw.
        with self.assertRaises(UnsafeBaseURLError):
            assert_safe_base_url("https://[::1")

    def test_rejects_localhost(self):
        with self.assertRaises(UnsafeBaseURLError):
            assert_safe_base_url("https://localhost")

    def test_rejects_loopback_ip(self):
        with self.assertRaises(UnsafeBaseURLError):
            assert_safe_base_url("https://127.0.0.1")

    def test_rejects_private_ip(self):
        with self.assertRaises(UnsafeBaseURLError):
            assert_safe_base_url("https://10.0.0.5")
        with self.assertRaises(UnsafeBaseURLError):
            assert_safe_base_url("https://192.168.1.1")

    def test_rejects_link_local_metadata_ip(self):
        # Cloud metadata endpoints (AWS/GCP/Azure) all live at this link-local address.
        with self.assertRaises(UnsafeBaseURLError):
            assert_safe_base_url("https://169.254.169.254")

    def test_rejects_metadata_hostname(self):
        with self.assertRaises(UnsafeBaseURLError):
            assert_safe_base_url("https://metadata.google.internal")

    def test_rejects_ipv6_loopback(self):
        with self.assertRaises(UnsafeBaseURLError):
            assert_safe_base_url("https://[::1]")

    def test_rejects_public_non_oracle_domain(self):
        with self.assertRaises(UnsafeBaseURLError):
            assert_safe_base_url("https://attacker.com")

    def test_rejects_lookalike_domain(self):
        # "notoraclecloud.com" is not a subdomain of "oraclecloud.com" and must be rejected.
        with self.assertRaises(UnsafeBaseURLError):
            assert_safe_base_url("https://evil.notoraclecloud.com")

    def test_rejects_public_ip(self):
        with self.assertRaises(UnsafeBaseURLError):
            assert_safe_base_url("https://8.8.8.8")

    def test_allows_default_https_port(self):
        self.assertEqual(
            assert_safe_base_url("https://example.oraclecloud.com:443"),
            "https://example.oraclecloud.com:443",
        )

    def test_rejects_non_standard_port(self):
        # An otherwise allow-listed host paired with a non-standard port
        # (e.g. an attacker-controlled listener fronting the same hostname)
        # must still be rejected.
        with self.assertRaises(UnsafeBaseURLError):
            assert_safe_base_url("https://demo.oraclecloud.com:8443")

    def test_rejects_invalid_port(self):
        with self.assertRaises(UnsafeBaseURLError):
            assert_safe_base_url("https://example.oraclecloud.com:999999")

    def test_rejects_backslash_host_bypass(self):
        # urlparse() keeps the backslash inside the hostname, so this string
        # ends with ".oraclecloud.com" and would otherwise pass the domain
        # allow-list. requests/urllib3 instead treat the backslash as the
        # end of the authority and send the request to host
        # "169.254.169.254" (the cloud metadata IP) -- a classic
        # parser-disagreement SSRF bypass. It must be rejected outright.
        with self.assertRaises(UnsafeBaseURLError):
            assert_safe_base_url("https://169.254.169.254\\foo.oraclecloud.com")

    def test_rejects_backslash_anywhere(self):
        with self.assertRaises(UnsafeBaseURLError):
            assert_safe_base_url("https://example.oraclecloud.com\\")


class TestBuildSafeSessionConnectionTimeIPValidation(unittest.TestCase):
    """An allow-listed Oracle hostname can still resolve to a private/
    link-local address (bad DNS config, or DNS rebinding). The session
    returned by build_safe_session() must refuse to connect in that case,
    and must do so before any outbound TCP connection is attempted.
    """

    @staticmethod
    def _fake_getaddrinfo(ip_address):
        def _getaddrinfo(host, port, *args, **kwargs):  # pylint: disable=unused-argument
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip_address, port))]

        return _getaddrinfo

    def test_rejects_allowlisted_host_resolving_to_loopback(self):
        session = build_safe_session()
        with patch(
            "tap_oracle_fusion.url_safety.socket.getaddrinfo",
            side_effect=self._fake_getaddrinfo("127.0.0.1"),
        ), patch(
            "tap_oracle_fusion.url_safety.urllib3_connection.create_connection"
        ) as mock_create_connection:
            with self.assertRaises(UnsafeBaseURLError):
                session.get("https://evil-but-allowlisted.oraclecloud.com/resource")
        # The request must be refused before any outbound socket is opened.
        mock_create_connection.assert_not_called()

    def test_rejects_allowlisted_host_resolving_to_link_local_metadata_ip(self):
        session = build_safe_session()
        with patch(
            "tap_oracle_fusion.url_safety.socket.getaddrinfo",
            side_effect=self._fake_getaddrinfo("169.254.169.254"),
        ), patch(
            "tap_oracle_fusion.url_safety.urllib3_connection.create_connection"
        ) as mock_create_connection:
            with self.assertRaises(UnsafeBaseURLError):
                session.get("https://evil-but-allowlisted.oraclecloud.com/resource")
        mock_create_connection.assert_not_called()

    def test_rejects_allowlisted_host_resolving_to_shared_address_space(self):
        # RFC 6598 carrier-grade NAT space (100.64.0.0/10): CPython's
        # ipaddress.is_private/is_reserved both miss this range, so it must
        # be caught by the is_global check instead.
        session = build_safe_session()
        with patch(
            "tap_oracle_fusion.url_safety.socket.getaddrinfo",
            side_effect=self._fake_getaddrinfo("100.64.0.1"),
        ), patch(
            "tap_oracle_fusion.url_safety.urllib3_connection.create_connection"
        ) as mock_create_connection:
            with self.assertRaises(UnsafeBaseURLError):
                session.get("https://evil-but-allowlisted.oraclecloud.com/resource")
        mock_create_connection.assert_not_called()


class TestResolveToPublicIp(unittest.TestCase):
    """Direct regression tests for the resolver-level IP validation."""

    @staticmethod
    def _fake_getaddrinfo(ip_address):
        def _getaddrinfo(host, port, *args, **kwargs):  # pylint: disable=unused-argument
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip_address, port))]

        return _getaddrinfo

    def test_rejects_shared_address_space(self):
        with patch(
            "tap_oracle_fusion.url_safety.socket.getaddrinfo",
            side_effect=self._fake_getaddrinfo("100.64.0.1"),
        ):
            with self.assertRaises(UnsafeBaseURLError):
                _resolve_to_public_ip("evil-but-allowlisted.oraclecloud.com", 443)

    def test_allows_public_ip(self):
        with patch(
            "tap_oracle_fusion.url_safety.socket.getaddrinfo",
            side_effect=self._fake_getaddrinfo("8.8.8.8"),
        ):
            self.assertEqual(
                _resolve_to_public_ip("example.oraclecloud.com", 443), "8.8.8.8"
            )

    def test_is_public_ip_rejects_shared_address_space_boundaries(self):
        self.assertFalse(_is_public_ip("100.64.0.0"))
        self.assertFalse(_is_public_ip("100.64.0.1"))
        self.assertFalse(_is_public_ip("100.127.255.254"))

    def test_is_public_ip_allows_addresses_just_outside_shared_space(self):
        self.assertTrue(_is_public_ip("100.63.255.255"))
        self.assertTrue(_is_public_ip("100.128.0.0"))

    def test_is_public_ip_rejects_multicast(self):
        self.assertFalse(_is_public_ip("224.0.0.251"))
