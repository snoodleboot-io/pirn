"""Unit tests for :class:`ShopifyClient`.

Uses an injected stub mirroring the
``shopify.ShopifyResource.connection.request`` surface. No real Shopify
store or network needed.
"""

from __future__ import annotations

from typing import Any

import pytest

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.saas.shopify_client import ShopifyClient
from pirn.domains.connectors.saas.shopify_config import ShopifyConfig


# ──────────────────────────────────────────────────────────── fake client


class FakeShopifyConnection:
    """Mirrors the ``connection.request`` slice of the Shopify SDK."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.response: dict[str, Any] = {"products": []}
        self.closed = False

    def request(
        self,
        method: str,
        path: str,
        headers: dict[str, str] | None = None,
        data: Any = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {"method": method, "path": path, "headers": headers, "data": data}
        )
        return self.response

    def close(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── conformance


def test_implements_api_client() -> None:
    client = ShopifyClient(client=FakeShopifyConnection())
    assert isinstance(client, ApiClient)


def test_construction_requires_config_or_client() -> None:
    with pytest.raises(TypeError, match="config= or client="):
        ShopifyClient()


def test_sensitive_fields_declared() -> None:
    cfg = ShopifyConfig()
    assert "access_token" in cfg.sensitive_fields


# ────────────────────────────────────────────────────────── delegation


@pytest.mark.asyncio
class TestRequest:
    async def test_get_appends_query_string_from_params(self) -> None:
        fake = FakeShopifyConnection()
        client = ShopifyClient(client=fake)
        result = await client.request(
            "GET", "/admin/api/2024-04/products.json", params={"a": 1}
        )
        assert result == fake.response
        assert fake.calls[0]["method"] == "GET"
        assert fake.calls[0]["path"] == "/admin/api/2024-04/products.json?a=1"
        assert fake.calls[0]["data"] is None

    async def test_post_passes_body_as_data(self) -> None:
        fake = FakeShopifyConnection()
        client = ShopifyClient(client=fake)
        await client.request(
            "POST",
            "/admin/api/2024-04/products.json",
            body={"product": {"title": "T"}},
        )
        assert fake.calls[0]["method"] == "POST"
        assert fake.calls[0]["data"] == {"product": {"title": "T"}}

    async def test_request_returns_stub_response(self) -> None:
        fake = FakeShopifyConnection()
        fake.response = {"product": {"id": 1}}
        client = ShopifyClient(client=fake)
        result = await client.request("GET", "/admin/api/2024-04/products/1.json")
        assert result == {"product": {"id": 1}}


# ─────────────────────────────────────────────────────────────── lifecycle


@pytest.mark.asyncio
class TestLifecycle:
    async def test_close_closes_underlying_client(self) -> None:
        fake = FakeShopifyConnection()
        client = ShopifyClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = ShopifyClient(client=FakeShopifyConnection())
        await client.close()
        await client.close()

    async def test_request_after_close_raises(self) -> None:
        client = ShopifyClient(client=FakeShopifyConnection())
        await client.close()
        with pytest.raises(RuntimeError, match="closed"):
            await client.request("GET", "/admin/api/2024-04/products.json")


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety:
    def test_repr_redacts_access_token(self) -> None:
        cfg = ShopifyConfig(
            shop_url="my-store.myshopify.com",
            access_token="shpat_leaks",
        )
        text = repr(cfg)
        assert "shpat_leaks" not in text
        assert "<redacted>" in text
