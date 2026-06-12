"""Unit tests for :class:`AlationClient`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.connectors.api_client import ApiClient
from pirn.connectors.bi_catalog.alation_client import AlationClient
from pirn.connectors.bi_catalog.alation_config import AlationConfig
from pirn.connectors.capabilities.metadata_catalog import (
    MetadataCatalog,
)
from pirn.connectors.capabilities.table_source import TableSource


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
        return FakeResponse(self.responses.get((method, url), {"ok": True}))

    async def aclose(self) -> None:
        self.closed = True



class _StandaloneTests(unittest.TestCase):
    def test_implements_api_client(self) -> None:
        client = AlationClient(client=FakeHttpx())
        assert isinstance(client, ApiClient)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            AlationClient()
    
    
    def test_sensitive_fields_listed(self) -> None:
        assert AlationConfig.sensitive_fields == ("refresh_token",)
    
    
class TestRequest(unittest.IsolatedAsyncioTestCase):
    async def test_request_builds_full_url_and_returns_json(self) -> None:
        fake = FakeHttpx()
        cfg = AlationConfig(
            base_url="https://alation.acme.com",
            refresh_token="rt",
            user_id=42,
        )
        fake.responses[
            ("GET", "https://alation.acme.com/integration/v1/datasource")
        ] = {"items": [{"id": 1}]}
        client = AlationClient(cfg, client=fake)

        result = await client.request(
            "GET", "/integration/v1/datasource", params={"a": 1}
        )

        assert result == {"items": [{"id": 1}]}
        assert fake.calls == [
            {
                "method": "GET",
                "url": "https://alation.acme.com/integration/v1/datasource",
                "params": {"a": 1},
                "json": None,
                "headers": None,
            }
        ]


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_underlying_client(self) -> None:
        fake = FakeHttpx()
        client = AlationClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = AlationClient(client=FakeHttpx())
        await client.close()
        await client.close()

    async def test_request_after_close_raises(self) -> None:
        client = AlationClient(client=FakeHttpx())
        await client.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await client.request("GET", "/integration/v1/datasource")


    def test_implements_table_source_and_metadata_catalog(self) -> None:
        client = AlationClient(client=FakeHttpx())
        assert isinstance(client, TableSource)
        assert isinstance(client, MetadataCatalog)
    
    
    def test_default_entity_type_is_data(self) -> None:
        client = AlationClient(client=FakeHttpx())
        assert client.entity_type == "data"
    
    
    def test_blank_entity_type_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "entity_type"):
            AlationClient(client=FakeHttpx(), entity_type="")
    
    
class TestFetchPage(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_page_uses_skip_and_limit(self) -> None:
        fake = FakeHttpx()
        cfg = AlationConfig(
            base_url="https://alation.acme.com",
            refresh_token="rt",
            user_id=1,
        )
        fake.responses[
            ("GET", "https://alation.acme.com/integration/v1/data")
        ] = [{"id": 1}, {"id": 2}]
        client = AlationClient(cfg, client=fake)

        rows, cursor = await client.fetch_page(page_size=2)

        assert rows == [{"id": 1}, {"id": 2}]
        # 2 rows == limit; expect a next cursor
        assert cursor == "2"
        assert fake.calls[0]["params"] == {"skip": 0, "limit": 2}

    async def test_fetch_page_short_page_terminates(self) -> None:
        fake = FakeHttpx()
        cfg = AlationConfig(
            base_url="https://alation.acme.com",
            refresh_token="rt",
            user_id=1,
        )
        fake.responses[
            ("GET", "https://alation.acme.com/integration/v1/data")
        ] = [{"id": 1}]
        client = AlationClient(cfg, client=fake)

        rows, cursor = await client.fetch_page(cursor="10", page_size=5)

        assert rows == [{"id": 1}]
        assert cursor is None
        assert fake.calls[0]["params"] == {"skip": 10, "limit": 5}


class TestListEntities(unittest.IsolatedAsyncioTestCase):
    async def test_paginates_internally(self) -> None:
        fake = FakeHttpx()
        cfg = AlationConfig(
            base_url="https://alation.acme.com",
            refresh_token="rt",
            user_id=1,
        )
        page_calls = {"count": 0}

        async def request_request(
            method: str,
            url: str,
            *,
            params: Any = None,
            json: Any = None,
            headers: Any = None,
        ) -> Any:
            fake.calls.append(
                {
                    "method": method,
                    "url": url,
                    "params": params,
                    "json": json,
                    "headers": headers,
                }
            )
            page_calls["count"] += 1
            if page_calls["count"] == 1:
                return _FakeJson(
                    [{"id": x} for x in range(100)]
                )
            return _FakeJson([{"id": 100}])

        fake.request = request_request  # type: ignore[assignment]
        client = AlationClient(cfg, client=fake)

        results = []
        async for entity in client.list_entities("data"):
            results.append(entity)

        assert len(results) == 101
        assert page_calls["count"] == 2

    async def test_filter_applied(self) -> None:
        fake = FakeHttpx()
        cfg = AlationConfig(
            base_url="https://alation.acme.com",
            refresh_token="rt",
            user_id=1,
        )
        fake.responses[
            ("GET", "https://alation.acme.com/integration/v1/data")
        ] = [
            {"id": 1, "kind": "table"},
            {"id": 2, "kind": "column"},
        ]
        client = AlationClient(cfg, client=fake)

        results = []
        async for entity in client.list_entities(
            "data", filter={"kind": "table"}
        ):
            results.append(entity)

        assert results == [{"id": 1, "kind": "table"}]


class TestDescribeEntity(unittest.IsolatedAsyncioTestCase):
    async def test_describe_calls_entity_get(self) -> None:
        fake = FakeHttpx()
        cfg = AlationConfig(
            base_url="https://alation.acme.com",
            refresh_token="rt",
            user_id=1,
        )
        fake.responses[
            ("GET", "https://alation.acme.com/integration/v1/data/42")
        ] = {"id": 42, "name": "ds"}
        client = AlationClient(cfg, client=fake)

        result = await client.describe_entity("42")

        assert result == {"id": 42, "name": "ds"}


class _FakeJson:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def json(self) -> Any:
        return self._payload
