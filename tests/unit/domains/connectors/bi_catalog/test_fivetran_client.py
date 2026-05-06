"""Unit tests for :class:`FivetranClient`.

Uses an injected stub client whose ``request`` mirrors the slice of
``httpx.AsyncClient`` the connector calls. No real Fivetran account
needed.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.bi_catalog.fivetran_client import FivetranClient
from pirn.domains.connectors.bi_catalog.fivetran_config import FivetranConfig
from pirn.domains.connectors.capabilities.table_source import TableSource

# ──────────────────────────────────────────────────────────── fake client


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

    async def request(
        self, method: str, url: str, *, params: Any = None, json: Any = None, headers: Any = None,
    ) -> FakeResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": params,
                "json": json,
                "headers": headers,
            }
        )
        payload = self.responses.get((method, url), {"ok": True})
        return FakeResponse(payload)

    async def aclose(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_api_client(self) -> None:
        client = FivetranClient(client=FakeHttpx())
        assert isinstance(client, ApiClient)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            FivetranClient()
    
    
    def test_sensitive_fields_listed(self) -> None:
        assert FivetranConfig.sensitive_fields == ("api_key", "api_secret")
    
    
# ────────────────────────────────────────────────────────────── dispatch


class TestRequest(unittest.IsolatedAsyncioTestCase):
    async def test_request_builds_full_url_and_returns_json(self) -> None:
        fake = FakeHttpx()
        cfg = FivetranConfig(
            api_key="k", api_secret="s", base_url="https://api.fivetran.com/v1"
        )
        fake.responses[
            ("GET", "https://api.fivetran.com/v1/connectors")
        ] = {"data": [{"id": "abc"}]}
        client = FivetranClient(cfg, client=fake)

        result = await client.request(
            "GET", "/connectors", params={"a": 1}
        )

        assert result == {"data": [{"id": "abc"}]}
        assert fake.calls == [
            {
                "method": "GET",
                "url": "https://api.fivetran.com/v1/connectors",
                "params": {"a": 1},
                "json": None,
                "headers": None,
            }
        ]

    async def test_request_passes_body_and_headers(self) -> None:
        fake = FakeHttpx()
        cfg = FivetranConfig(api_key="k", api_secret="s")
        client = FivetranClient(cfg, client=fake)

        await client.request(
            "POST",
            "/connectors",
            body={"service": "snowflake"},
            headers={"X-Trace": "1"},
        )

        assert fake.calls[0]["method"] == "POST"
        assert fake.calls[0]["json"] == {"service": "snowflake"}
        assert fake.calls[0]["headers"] == {"X-Trace": "1"}


# ─────────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_underlying_client(self) -> None:
        fake = FakeHttpx()
        client = FivetranClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = FivetranClient(client=FakeHttpx())
        await client.close()
        await client.close()

    async def test_request_after_close_raises(self) -> None:
        client = FivetranClient(client=FakeHttpx())
        await client.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await client.request("GET", "/connectors")


# ─────────────────────────────────────────────────────── table source surface


    def test_implements_table_source(self) -> None:
        client = FivetranClient(client=FakeHttpx())
        assert isinstance(client, TableSource)
    
    
    def test_default_resource_is_connectors(self) -> None:
        client = FivetranClient(client=FakeHttpx())
        assert client.resource == "connectors"
    
    
    def test_blank_resource_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "resource"):
            FivetranClient(client=FakeHttpx(), resource="")
    
    
class TestFetchPage(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_page_returns_rows_and_next_cursor(self) -> None:
        fake = FakeHttpx()
        cfg = FivetranConfig(
            api_key="k",
            api_secret="s",
            base_url="https://api.fivetran.com/v1",
        )
        fake.responses[
            ("GET", "https://api.fivetran.com/v1/connectors")
        ] = {
            "data": {
                "items": [{"id": "abc"}, {"id": "def"}],
                "next_cursor": "tok2",
            }
        }
        client = FivetranClient(cfg, client=fake)

        rows, cursor = await client.fetch_page(
            cursor="tok1", page_size=10
        )

        assert rows == [{"id": "abc"}, {"id": "def"}]
        assert cursor == "tok2"
        assert fake.calls[0]["params"] == {"cursor": "tok1", "limit": 10}

    async def test_fetch_page_no_next_cursor_returns_none(self) -> None:
        fake = FakeHttpx()
        cfg = FivetranConfig(
            api_key="k",
            api_secret="s",
            base_url="https://api.fivetran.com/v1",
        )
        fake.responses[
            ("GET", "https://api.fivetran.com/v1/connectors")
        ] = {"data": {"items": [{"id": "abc"}]}}
        client = FivetranClient(cfg, client=fake)

        _, cursor = await client.fetch_page()

        assert cursor is None


class TestVendorTypedListings(unittest.IsolatedAsyncioTestCase):
    async def test_list_connectors_targets_connectors(self) -> None:
        fake = FakeHttpx()
        cfg = FivetranConfig(
            api_key="k",
            api_secret="s",
            base_url="https://api.fivetran.com/v1",
        )
        fake.responses[
            ("GET", "https://api.fivetran.com/v1/connectors")
        ] = {"data": {"items": [{"id": "abc"}]}}
        client = FivetranClient(cfg, client=fake)

        rows, _ = await client.list_connectors(limit=5)

        assert rows == [{"id": "abc"}]
        assert fake.calls[0]["url"].endswith("/connectors")

    async def test_list_groups_targets_groups(self) -> None:
        fake = FakeHttpx()
        cfg = FivetranConfig(
            api_key="k",
            api_secret="s",
            base_url="https://api.fivetran.com/v1",
        )
        fake.responses[
            ("GET", "https://api.fivetran.com/v1/groups")
        ] = {"data": {"items": [{"id": "g1"}]}}
        client = FivetranClient(cfg, client=fake)

        rows, _ = await client.list_groups()

        assert rows == [{"id": "g1"}]
        assert fake.calls[0]["url"].endswith("/groups")
