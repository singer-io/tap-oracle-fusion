"""Tests for tap_oracle_fusion.url_safety SSRF guard."""
import unittest

from tap_oracle_fusion.url_safety import assert_safe_base_url, UnsafeBaseURLError


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


if __name__ == "__main__":
    unittest.main()

