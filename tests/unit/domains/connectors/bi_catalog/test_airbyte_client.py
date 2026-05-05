"""Unit tests for :class:`AirbyteClient`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.bi_catalog.airbyte_client import AirbyteClient
from pirn.domains.connectors.bi_catalog.airbyte_config import AirbyteConfig
from pirn.domains.connectors.capabilities.table_source import TableSource


class FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def json(self) -> Any:
        return self._payload


class FakeHttpx:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.responses: dict[tuple[str, str], Any] = {}
        self.closed = False

    async def request(self, method: str, url: str, *, params: Any = None, json: Any = None, headers: Any = None,) -> FakeResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": params,
                "json": json,
                "headers": headers,
            }
        )
        return FakeResponse(self.responses.get((method, url), {"ok": True}))

    async def aclose(self) -> None:
        self.closed = True



class _StandaloneTests(unittest.TestCase):
    def test_implements_api_client(self) -> None:
        client = AirbyteClient(client=FakeHttpx())
        assert isinstance(client, ApiClient)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            AirbyteClient()
    
    
    def test_sensitive_fields_listed(self) -> None:
        assert AirbyteConfig.sensitive_fields == ("client_secret", "access_token")
    
    
class TestRequest(unittest.IsolatedAsyncioTestCase):
    async def test_request_builds_full_url_and_returns_json(self) -> None:
        fake = FakeHttpx()
        cfg = AirbyteConfig(
            base_url="https://api.airbyte.com/v1",
            access_token="tok",
        )
        fake.responses[
            ("GET", "https://api.airbyte.com/v1/sources")
        ] = {"sources": []}
        client = AirbyteClient(cfg, client=fake)

        result = await client.request("GET", "/sources", params={"a": 1})

        assert result == {"sources": []}
        assert fake.calls == [
            {
                "method": "GET",
                "url": "https://api.airbyte.com/v1/sources",
                "params": {"a": 1},
                "json": None,
                "headers": None,
            }
        ]

    async def test_request_post_with_body(self) -> None:
        fake = FakeHttpx()
        client = AirbyteClient(
            AirbyteConfig(access_token="tok"), client=fake
        )

        await client.request(
            "POST", "/sources", body={"name": "s3"}
        )

        assert fake.calls[0]["method"] == "POST"
        assert fake.calls[0]["json"] == {"name": "s3"}


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_underlying_client(self) -> None:
        fake = FakeHttpx()
        client = AirbyteClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = AirbyteClient(client=FakeHttpx())
        await client.close()
        await client.close()

    async def test_request_after_close_raises(self) -> None:
        client = AirbyteClient(client=FakeHttpx())
        await client.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await client.request("GET", "/sources")


    def test_implements_table_source(self) -> None:
        client = AirbyteClient(client=FakeHttpx())
        assert isinstance(client, TableSource)
    
    
    def test_default_resource_is_connections(self) -> None:
        client = AirbyteClient(client=FakeHttpx())
        assert client.resource == "connections"
    
    
    def test_blank_resource_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "resource"):
            AirbyteClient(client=FakeHttpx(), resource="")
    
    
class TestFetchPage(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_page_posts_to_list_endpoint(self) -> None:
        fake = FakeHttpx()
        cfg = AirbyteConfig(
            base_url="https://api.airbyte.com",
            access_token="tok",
        )
        fake.responses[
            ("POST", "https://api.airbyte.com/v1/connections/list")
        ] = {
            "data": [{"id": "c1"}, {"id": "c2"}],
            "next_cursor": "next-tok",
        }
        client = AirbyteClient(cfg, client=fake)

        rows, cursor = await client.fetch_page(
            cursor="prev-tok", page_size=20
        )

        assert rows == [{"id": "c1"}, {"id": "c2"}]
        assert cursor == "next-tok"
        assert fake.calls[0]["method"] == "POST"
        assert fake.calls[0]["json"] == {
            "limit": 20,
            "cursor": "prev-tok",
        }

    async def test_fetch_page_no_next_cursor_returns_none(self) -> None:
        fake = FakeHttpx()
        cfg = AirbyteConfig(
            base_url="https://api.airbyte.com", access_token="tok"
        )
        fake.responses[
            ("POST", "https://api.airbyte.com/v1/connections/list")
        ] = {"data": [{"id": "c1"}]}
        client = AirbyteClient(cfg, client=fake)

        _, cursor = await client.fetch_page()

        assert cursor is None


class TestVendorTypedListings(unittest.IsolatedAsyncioTestCase):
    async def test_list_connections(self) -> None:
        fake = FakeHttpx()
        cfg = AirbyteConfig(
            base_url="https://api.airbyte.com", access_token="tok"
        )
        fake.responses[
            ("POST", "https://api.airbyte.com/v1/connections/list")
        ] = {"data": [{"id": "c1"}]}
        client = AirbyteClient(cfg, client=fake)

        rows, _ = await client.list_connections(limit=5)

        assert rows == [{"id": "c1"}]
        assert fake.calls[0]["url"].endswith("/v1/connections/list")
        assert fake.calls[0]["json"] == {"limit": 5}

    async def test_list_workspaces(self) -> None:
        fake = FakeHttpx()
        cfg = AirbyteConfig(
            base_url="https://api.airbyte.com", access_token="tok"
        )
        fake.responses[
            ("POST", "https://api.airbyte.com/v1/workspaces/list")
        ] = {"data": [{"id": "w1"}]}
        client = AirbyteClient(cfg, client=fake)

        rows, _ = await client.list_workspaces()

        assert rows == [{"id": "w1"}]
        assert fake.calls[0]["url"].endswith("/v1/workspaces/list")
