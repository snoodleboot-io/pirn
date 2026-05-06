"""Unit tests for :class:`StripeClient`.

Uses an injected stub client mirroring ``stripe.StripeClient.raw_request``.
No real Stripe account or network needed.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.saas.stripe_client import StripeClient
from pirn.domains.connectors.saas.stripe_config import StripeConfig

# ──────────────────────────────────────────────────────────── fake client


class FakeStripeClient:
    """Mirrors the ``raw_request`` slice of the Stripe SDK."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.response: dict[str, Any] = {"object": "list", "data": []}
        self.closed = False

    def raw_request(
        self, method: str, path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "method": method,
                "path": path,
                "params": params,
                "body": body,
                "headers": headers,
            }
        )
        return self.response

    def close(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_api_client(self) -> None:
        client = StripeClient(client=FakeStripeClient())
        assert isinstance(client, ApiClient)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            StripeClient()
    
    
    def test_sensitive_fields_declared(self) -> None:
        cfg = StripeConfig()
        assert "api_key" in cfg.sensitive_fields
    
    
# ────────────────────────────────────────────────────────── delegation


class TestRequest(unittest.IsolatedAsyncioTestCase):
    async def test_get_passes_method_path_params(self) -> None:
        fake = FakeStripeClient()
        client = StripeClient(client=fake)
        result = await client.request(
            "GET", "/v1/customers", params={"a": 1}
        )
        assert result == fake.response
        assert fake.calls == [
            {
                "method": "GET",
                "path": "/v1/customers",
                "params": {"a": 1},
                "body": None,
                "headers": None,
            }
        ]

    async def test_post_passes_body(self) -> None:
        fake = FakeStripeClient()
        client = StripeClient(client=fake)
        await client.request(
            "POST", "/v1/customers", body={"email": "a@b"}
        )
        assert fake.calls[0]["method"] == "POST"
        assert fake.calls[0]["body"] == {"email": "a@b"}

    async def test_request_returns_stub_response(self) -> None:
        fake = FakeStripeClient()
        fake.response = {"id": "cus_123"}
        client = StripeClient(client=fake)
        result = await client.request("GET", "/v1/customers/cus_123")
        assert result == {"id": "cus_123"}


# ─────────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_underlying_client(self) -> None:
        fake = FakeStripeClient()
        client = StripeClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = StripeClient(client=FakeStripeClient())
        await client.close()
        await client.close()

    async def test_request_after_close_raises(self) -> None:
        client = StripeClient(client=FakeStripeClient())
        await client.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await client.request("GET", "/v1/customers")


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_api_key(self) -> None:
        cfg = StripeConfig(api_key="sk_live_leaks")
        text = repr(cfg)
        assert "sk_live_leaks" not in text
        assert "<redacted>" in text
