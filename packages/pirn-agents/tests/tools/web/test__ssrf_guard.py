"""Unit tests for :class:`SsrfGuard` (PIR-741).

Covers the three properties the guard gained: every resolved address is
classified (not just the first), IPv4 and IPv6 are both classified, and a
:class:`VettedEndpoint` carrying the checked address is returned so callers can
pin to it.

The resolver is injected throughout — no test performs a DNS lookup.
"""

from __future__ import annotations

import unittest
import unittest.mock

from pirn_agents.tools.web._ssrf_guard import SsrfGuard
from pirn_agents.tools.web.vetted_endpoint import VettedEndpoint


class TestAllRecordsClassified(unittest.TestCase):
    """gethostbyname returned one A record; a mixed-record host used to pass."""

    def test_rejects_when_any_address_is_private(self) -> None:
        guard = SsrfGuard(resolver=lambda host: ("93.184.216.34", "10.0.0.1"))
        with self.assertRaisesRegex(ValueError, "private/loopback/link-local"):
            guard.assert_public_host("http://mixed.example/")

    def test_rejects_when_the_private_address_is_last(self) -> None:
        guard = SsrfGuard(resolver=lambda host: ("93.184.216.34", "8.8.8.8", "169.254.169.254"))
        with self.assertRaisesRegex(ValueError, "private/loopback/link-local"):
            guard.assert_public_host("http://mixed.example/")

    def test_accepts_when_every_address_is_public(self) -> None:
        guard = SsrfGuard(resolver=lambda host: ("93.184.216.34", "8.8.8.8"))
        endpoint = guard.assert_public_host("http://ok.example/")
        assert endpoint.address == "93.184.216.34"

    def test_single_string_resolver_still_supported(self) -> None:
        # The seam is widened, not broken: many injected resolvers return one str.
        guard = SsrfGuard(resolver=lambda host: "93.184.216.34")
        assert guard.assert_public_host("http://ok.example/").address == "93.184.216.34"

    def test_empty_resolution_is_rejected(self) -> None:
        guard = SsrfGuard(resolver=lambda host: ())
        with self.assertRaisesRegex(ValueError, "unresolvable host"):
            guard.assert_public_host("http://void.example/")


class TestIpv6Classified(unittest.TestCase):
    """gethostbyname was IPv4-only, so v6 failed closed as 'unresolvable'."""

    def test_rejects_v6_loopback(self) -> None:
        guard = SsrfGuard(resolver=lambda host: ("::1",))
        with self.assertRaisesRegex(ValueError, "private/loopback/link-local"):
            guard.assert_public_host("http://v6.example/")

    def test_rejects_v6_unique_local(self) -> None:
        guard = SsrfGuard(resolver=lambda host: ("fd00::1",))
        with self.assertRaisesRegex(ValueError, "private/loopback/link-local"):
            guard.assert_public_host("http://v6.example/")

    def test_rejects_v6_link_local(self) -> None:
        guard = SsrfGuard(resolver=lambda host: ("fe80::1",))
        with self.assertRaisesRegex(ValueError, "private/loopback/link-local"):
            guard.assert_public_host("http://v6.example/")

    def test_rejects_ipv4_mapped_metadata_address(self) -> None:
        # ::ffff:169.254.169.254 is link-local v4 wearing a v6 costume; the v6
        # predicates alone do not classify it, so it must be unmapped first.
        guard = SsrfGuard(resolver=lambda host: ("::ffff:169.254.169.254",))
        with self.assertRaisesRegex(ValueError, "private/loopback/link-local"):
            guard.assert_public_host("http://sneaky.example/")

    def test_accepts_public_v6(self) -> None:
        guard = SsrfGuard(resolver=lambda host: ("2606:2800:220:1:248:1893:25c8:1946",))
        endpoint = guard.assert_public_host("http://v6.example/")
        assert endpoint.address == "2606:2800:220:1:248:1893:25c8:1946"

    def test_rejects_v6_site_local(self) -> None:
        # fec0::/10 is reported as is_private=False AND is_global=True, so neither
        # the private predicates nor is_global catches it — it needs is_site_local.
        guard = SsrfGuard(resolver=lambda host: ("fec0::1",))
        with self.assertRaisesRegex(ValueError, "private/loopback/link-local"):
            guard.assert_public_host("http://sitelocal.example/")

    def test_rejects_carrier_grade_nat(self) -> None:
        # RFC 6598 100.64/10 is is_private=False; only is_global rejects it.
        guard = SsrfGuard(resolver=lambda host: ("100.64.0.1",))
        with self.assertRaisesRegex(ValueError, "private/loopback/link-local"):
            guard.assert_public_host("http://cgnat.example/")

    def test_rejects_unspecified_address(self) -> None:
        guard = SsrfGuard(resolver=lambda host: ("0.0.0.0",))
        with self.assertRaisesRegex(ValueError, "private/loopback/link-local"):
            guard.assert_public_host("http://zero.example/")


class TestVettedEndpointReturned(unittest.TestCase):
    def test_returns_endpoint_with_hostname_and_address(self) -> None:
        guard = SsrfGuard(resolver=lambda host: ("93.184.216.34",))
        endpoint = guard.assert_public_host("https://example.com/a/b?c=d")
        assert isinstance(endpoint, VettedEndpoint)
        assert endpoint.hostname == "example.com"
        assert endpoint.address == "93.184.216.34"
        assert endpoint.port is None

    def test_captures_explicit_port(self) -> None:
        guard = SsrfGuard(resolver=lambda host: ("93.184.216.34",))
        endpoint = guard.assert_public_host("https://example.com:8443/x")
        assert endpoint.port == 8443
        assert endpoint.host_header == "example.com:8443"

    def test_allow_private_still_returns_a_pinnable_endpoint(self) -> None:
        guard = SsrfGuard(allow_private=True, resolver=lambda host: ("10.0.0.1",))
        endpoint = guard.assert_public_host("http://internal.example/")
        assert endpoint.address == "10.0.0.1"


class TestExistingPolicyUnchanged(unittest.TestCase):
    def test_rejects_non_http_scheme(self) -> None:
        with self.assertRaisesRegex(ValueError, "only http\\(s\\)"):
            SsrfGuard().assert_public_host("ftp://example.com/x")

    def test_rejects_missing_hostname(self) -> None:
        with self.assertRaisesRegex(ValueError, "no hostname"):
            SsrfGuard().assert_public_host("http:///nohost")

    def test_rejects_host_outside_allowlist(self) -> None:
        guard = SsrfGuard(allowed_hosts=("example.com",), resolver=lambda host: ("93.184.216.34",))
        with self.assertRaisesRegex(ValueError, "not in allowed_hosts"):
            guard.assert_public_host("http://other.example/")

    def test_allowlist_checked_before_resolution(self) -> None:
        def _never(host: str) -> str:
            raise AssertionError("resolver must not run for a non-allow-listed host")

        guard = SsrfGuard(allowed_hosts=("example.com",), resolver=_never)
        with self.assertRaises(ValueError):
            guard.assert_public_host("http://other.example/")

    def test_resolver_failure_reported_as_unresolvable(self) -> None:
        def _boom(host: str) -> str:
            raise OSError("dns down")

        with self.assertRaisesRegex(ValueError, "unresolvable host"):
            SsrfGuard(resolver=_boom).assert_public_host("http://nope.invalid/")


class TestResolverBinding(unittest.TestCase):
    def test_default_resolver_is_looked_up_per_call(self) -> None:
        """A guard built before a patch must still honour it.

        Binding the default at construction would make patching ``_resolve_all``
        silently fall through to real DNS for any guard built in an ``__init__``.
        """
        guard = SsrfGuard()  # constructed BEFORE the patch below
        with unittest.mock.patch.object(
            SsrfGuard, "_resolve_all", staticmethod(lambda host: ("10.0.0.1",))
        ):
            with self.assertRaisesRegex(ValueError, "private/loopback/link-local"):
                guard.assert_public_host("http://late.example/")


class TestRebinding(unittest.TestCase):
    def test_guard_resolves_once_so_a_flipping_resolver_cannot_be_re_consulted(self) -> None:
        """The vetted address is captured, so there is no second lookup to poison.

        A short-TTL attacker record answers public to the guard and private to the
        client. Pinning removes the client's lookup entirely.
        """
        calls = 0

        def _rebinding(_host: str) -> str:
            nonlocal calls
            calls += 1
            return "93.184.216.34" if calls == 1 else "169.254.169.254"

        endpoint = SsrfGuard(resolver=_rebinding).assert_public_host("https://example.com/x")
        assert endpoint.address == "93.184.216.34"
        assert endpoint.pinned_url("https://example.com/x") == "https://93.184.216.34/x"
        # The point of the test: exactly one lookup happened, so the flipped answer
        # is unreachable. Without pinning the client would perform a second one.
        assert calls == 1


class TestPinning(unittest.TestCase):
    def test_refuses_to_pin_a_url_for_a_different_host(self) -> None:
        endpoint = VettedEndpoint(hostname="example.com", address="93.184.216.34")
        with self.assertRaisesRegex(ValueError, "refusing to pin"):
            endpoint.pinned_url("https://totally-different-host.evil/x")

    def test_pinned_url_swaps_host_and_keeps_everything_else(self) -> None:
        endpoint = VettedEndpoint(hostname="example.com", address="93.184.216.34")
        assert (
            endpoint.pinned_url("https://example.com/a/b?c=d#e")
            == "https://93.184.216.34/a/b?c=d#e"
        )

    def test_pinned_url_preserves_explicit_port(self) -> None:
        endpoint = VettedEndpoint(hostname="example.com", address="93.184.216.34", port=8443)
        assert endpoint.pinned_url("https://example.com:8443/x") == "https://93.184.216.34:8443/x"

    def test_pinned_url_brackets_ipv6(self) -> None:
        endpoint = VettedEndpoint(hostname="v6.example", address="2606:2800::1")
        assert endpoint.pinned_url("https://v6.example/x") == "https://[2606:2800::1]/x"

    def test_host_header_and_sni_preserve_the_real_name(self) -> None:
        # Without these, a pinned HTTPS request would fail certificate verification
        # and virtual-hosted origins would serve the wrong site.
        endpoint = VettedEndpoint(hostname="example.com", address="93.184.216.34")
        assert endpoint.request_headers()["Host"] == "example.com"
        assert endpoint.request_extensions == {"sni_hostname": "example.com"}

    def test_request_headers_merges_without_mutating_input(self) -> None:
        endpoint = VettedEndpoint(hostname="example.com", address="93.184.216.34")
        original = {"Accept": "text/plain"}
        merged = endpoint.request_headers(original)
        assert merged == {"Accept": "text/plain", "Host": "example.com"}
        assert original == {"Accept": "text/plain"}
