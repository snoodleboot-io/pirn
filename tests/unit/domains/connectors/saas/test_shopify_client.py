"""Unit tests for :class:`ShopifyClient`.

Uses an injected stub mirroring the
``shopify.ShopifyResource.connection.request`` surface. No real Shopify
store or network needed.
"""

from __future__ import annotations

from typing import Any
import unittest


from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.capabilities.table_source import TableSource
from pirn.domains.connectors.saas.shopify_client import ShopifyClient
from pirn.domains.connectors.saas.shopify_config import ShopifyConfig


# ──────────────────────────────────────────────────────────── fake client


class FakeShopifyConnection:
    """Mirrors the ``connection.request`` slice of the Shopify SDK."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.response: dict[str, Any] = {"products": []}
        self.closed = False

    def request(self, method: str, path: str, headers: dict[str, str] | None = None, data: Any = None,) -> dict[str, Any]:
        self.calls.append(
            {"method": method, "path": path, "headers": headers, "data": data}
        )
        return self.response

    def close(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_api_client(self) -> None:
        client = ShopifyClient(client=FakeShopifyConnection())
        assert isinstance(client, ApiClient)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            ShopifyClient()
    
    
    def test_sensitive_fields_declared(self) -> None:
        cfg = ShopifyConfig()
        assert "access_token" in cfg.sensitive_fields
    
    
# ────────────────────────────────────────────────────────── delegation


class TestRequest(unittest.IsolatedAsyncioTestCase):
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


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
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
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await client.request("GET", "/admin/api/2024-04/products.json")


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_access_token(self) -> None:
        cfg = ShopifyConfig(
            shop_url="my-store.myshopify.com",
            access_token="shpat_leaks",
        )
        text = repr(cfg)
        assert "shpat_leaks" not in text
        assert "<redacted>" in text


# ───────────────────────────────────────────────────────── capability mixins


class FakeShopifyResponse:
    """Mimics a Shopify SDK HTTP response with a body dict and headers."""

    def __init__(self, body: dict[str, Any], headers: dict[str, str] | None = None,) -> None:
        self.body = body
        self.headers = headers or {}


class FakeShopifyConnectionWithHeaders:
    """Fake whose ``request`` returns objects exposing ``.body``/``.headers``."""

    def __init__(self, response: Any) -> None:
        self.calls: list[dict[str, Any]] = []
        self.response: Any = response
        self.closed = False

    def request(self, method: str, path: str, headers: dict[str, str] | None = None, data: Any = None,) -> Any:
        self.calls.append(
            {"method": method, "path": path, "headers": headers, "data": data}
        )
        return self.response

    def close(self) -> None:
        self.closed = True


    def test_implements_table_source(self) -> None:
        client = ShopifyClient(client=FakeShopifyConnection())
        assert isinstance(client, TableSource)
    
    
    def test_default_resource_is_orders(self) -> None:
        client = ShopifyClient(client=FakeShopifyConnection())
        assert client.resource == "orders"
    
    
    def test_construction_rejects_empty_resource(self) -> None:
        with self.assertRaisesRegex(ValueError, "resource"):
            ShopifyClient(client=FakeShopifyConnection(), resource="")
    
    
class TestFetchPage(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_page_returns_orders_no_link(self) -> None:
        fake = FakeShopifyConnection()
        fake.response = {"orders": [{"id": 1}, {"id": 2}]}
        client = ShopifyClient(client=fake)
        rows, cursor = await client.fetch_page()
        assert rows == [{"id": 1}, {"id": 2}]
        assert cursor is None
        assert fake.calls[0]["path"].startswith("/admin/api/")
        assert fake.calls[0]["path"].endswith("/orders.json")

    async def test_fetch_page_extracts_cursor_from_link_header(self,) -> None:
        link = (
            '<https://shop.myshopify.com/admin/api/2024-04/orders.json'
            '?page_info=NEXT_TOKEN_42&limit=50>; rel="next"'
        )
        fake_response = FakeShopifyResponse(
            body={"orders": [{"id": 1}]},
            headers={"Link": link},
        )
        fake = FakeShopifyConnectionWithHeaders(fake_response)
        client = ShopifyClient(client=fake)
        rows, cursor = await client.fetch_page(page_size=50)
        assert rows == [{"id": 1}]
        assert cursor == "NEXT_TOKEN_42"
        assert "limit=50" in fake.calls[0]["path"]

    async def test_fetch_page_with_cursor_passes_page_info(self) -> None:
        fake = FakeShopifyConnection()
        fake.response = {"orders": []}
        client = ShopifyClient(client=fake)
        await client.fetch_page("TOK_99", page_size=25)
        path = fake.calls[0]["path"]
        assert "page_info=TOK_99" in path
        assert "limit=25" in path

    async def test_fetch_page_uses_configured_resource(self) -> None:
        fake = FakeShopifyConnection()
        fake.response = {"products": [{"id": 9}]}
        client = ShopifyClient(client=fake, resource="products")
        rows, cursor = await client.fetch_page()
        assert rows == [{"id": 9}]
        assert cursor is None
        assert fake.calls[0]["path"].endswith("/products.json")

    async def test_fetch_page_link_header_without_next_returns_none(self,) -> None:
        link = (
            '<https://shop.myshopify.com/admin/api/2024-04/orders.json'
            '?page_info=PREV>; rel="previous"'
        )
        fake_response = FakeShopifyResponse(
            body={"orders": [{"id": 1}]},
            headers={"Link": link},
        )
        fake = FakeShopifyConnectionWithHeaders(fake_response)
        client = ShopifyClient(client=fake)
        rows, cursor = await client.fetch_page()
        assert rows == [{"id": 1}]
        assert cursor is None


class TestVendorListShortcuts(unittest.IsolatedAsyncioTestCase):
    async def test_list_orders(self) -> None:
        fake = FakeShopifyConnection()
        fake.response = {"orders": [{"id": 1}]}
        client = ShopifyClient(client=fake)
        rows, cursor = await client.list_orders()
        assert rows == [{"id": 1}]
        assert cursor is None
        assert fake.calls[0]["path"].endswith("/orders.json")

    async def test_list_products(self) -> None:
        fake = FakeShopifyConnection()
        fake.response = {"products": [{"id": 7}]}
        client = ShopifyClient(client=fake)
        rows, cursor = await client.list_products()
        assert rows == [{"id": 7}]
        assert cursor is None
        assert fake.calls[0]["path"].endswith("/products.json")
