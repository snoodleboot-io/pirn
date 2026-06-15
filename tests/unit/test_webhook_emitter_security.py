"""Security tests for WebhookEmitter — TLS config (M-6) and SSRF guard (L-10)."""

from __future__ import annotations

import ssl
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from pirn.emitters.webhook import WebhookEmitter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_client() -> MagicMock:
    mock = MagicMock()
    mock.aclose = AsyncMock()
    return mock


# ---------------------------------------------------------------------------
# M-6: TLS configuration
# ---------------------------------------------------------------------------



class _StandaloneTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_verify_true_passed_to_httpx(self) -> None:
        """Default verify=True is forwarded to httpx.AsyncClient."""
        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _make_mock_client()
            emitter = WebhookEmitter(url_status="https://example.com/hook")
            await emitter._ensure_client()
            _, kwargs = mock_cls.call_args
            assert kwargs.get("verify") is True
    
    
    async def test_custom_ca_bundle_path_passed_as_verify(self) -> None:
        """A CA bundle path string is passed as verify= to httpx.AsyncClient."""
        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _make_mock_client()
            emitter = WebhookEmitter(
                url_status="https://example.com/hook",
                verify="/etc/ssl/certs/ca-certificates.crt",
            )
            await emitter._ensure_client()
            _, kwargs = mock_cls.call_args
            assert kwargs.get("verify") == "/etc/ssl/certs/ca-certificates.crt"
    
    
    async def test_ssl_context_passed_as_verify_to_httpx(self) -> None:
        """An ssl.SSLContext supplied via ssl_context= is forwarded as verify=."""
        ctx = ssl.create_default_context()
        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _make_mock_client()
            emitter = WebhookEmitter(
                url_status="https://example.com/hook",
                ssl_context=ctx,
            )
            await emitter._ensure_client()
            _, kwargs = mock_cls.call_args
            assert kwargs.get("verify") is ctx
    
    
# ---------------------------------------------------------------------------
# L-10: SSRF / scheme guard
# ---------------------------------------------------------------------------


    def test_non_http_scheme_raises_at_construction(self) -> None:
        """A non-http/https scheme raises ValueError immediately."""
        with self.assertRaisesRegex(ValueError, r"scheme.*not permitted"):
            WebhookEmitter(url_status="ftp://example.com/hook")
    
    
    def test_private_ip_raises_when_block_private_ips_true(self) -> None:
        """A private IP URL raises ValueError when block_private_ips=True."""
        with self.assertRaisesRegex(ValueError, "private/loopback"):
            WebhookEmitter(
                url_status="http://192.168.1.1/hook",
                block_private_ips=True,
            )
    
    
    def test_loopback_raises_when_block_private_ips_true(self) -> None:
        """A loopback IP URL raises ValueError when block_private_ips=True."""
        with self.assertRaisesRegex(ValueError, "private/loopback"):
            WebhookEmitter(
                url_status="http://127.0.0.1/hook",
                block_private_ips=True,
            )
    
    
    def test_private_ip_allowed_when_block_private_ips_false(self) -> None:
        """A private IP URL is accepted when block_private_ips=False (default)."""
        emitter = WebhookEmitter(url_status="http://192.168.1.1/hook")
        assert emitter._url_status == "http://192.168.1.1/hook"
    
    
    def test_public_url_always_allowed(self) -> None:
        """A public HTTPS URL is accepted unconditionally."""
        emitter = WebhookEmitter(
            url_status="https://example.com/hook",
            block_private_ips=True,
        )
        assert emitter._url_status == "https://example.com/hook"
