"""Unit tests for :class:`OpenMetadataClient`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.bi_catalog.open_metadata_client import (
    OpenMetadataClient,
)
from pirn.domains.connectors.bi_catalog.open_metadata_config import (
    OpenMetadataConfig,
)
from pirn.domains.connectors.capabilities.metadata_catalog import (
    MetadataCatalog,
)
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
        client = OpenMetadataClient(client=FakeHttpx())
        assert isinstance(client, ApiClient)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            OpenMetadataClient()
    
    
    def test_sensitive_fields_listed(self) -> None:
        assert OpenMetadataConfig.sensitive_fields == ("jwt_token",)
    
    
class TestRequest(unittest.IsolatedAsyncioTestCase):
    async def test_request_builds_full_url_and_returns_json(self) -> None:
        fake = FakeHttpx()
        cfg = OpenMetadataConfig(
            host_url="https://om.acme.com/api", jwt_token="jwt"
        )
        fake.responses[
            ("GET", "https://om.acme.com/api/v1/tables")
        ] = {"data": [{"name": "t1"}]}
        client = OpenMetadataClient(cfg, client=fake)

        result = await client.request(
            "GET", "/v1/tables", params={"a": 1}
        )

        assert result == {"data": [{"name": "t1"}]}
        assert fake.calls == [
            {
                "method": "GET",
                "url": "https://om.acme.com/api/v1/tables",
                "params": {"a": 1},
                "json": None,
                "headers": None,
            }
        ]


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_underlying_client(self) -> None:
        fake = FakeHttpx()
        client = OpenMetadataClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = OpenMetadataClient(client=FakeHttpx())
        await client.close()
        await client.close()

    async def test_request_after_close_raises(self) -> None:
        client = OpenMetadataClient(client=FakeHttpx())
        await client.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await client.request("GET", "/v1/tables")


    def test_implements_table_source_and_metadata_catalog(self) -> None:
        client = OpenMetadataClient(client=FakeHttpx())
        assert isinstance(client, TableSource)
        assert isinstance(client, MetadataCatalog)
    
    
    def test_default_entity_type_is_tables(self) -> None:
        client = OpenMetadataClient(client=FakeHttpx())
        assert client.entity_type == "tables"
    
    
    def test_blank_entity_type_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "entity_type"):
            OpenMetadataClient(client=FakeHttpx(), entity_type="")
    
    
class TestVendorTypedListings(unittest.IsolatedAsyncioTestCase):
    async def test_list_tables_passes_paging_params(self) -> None:
        fake = FakeHttpx()
        cfg = OpenMetadataConfig(
            host_url="https://om.acme.com", jwt_token="jwt"
        )
        fake.responses[
            ("GET", "https://om.acme.com/api/v1/tables")
        ] = {
            "data": [{"name": "t1"}, {"name": "t2"}],
            "paging": {"after": "next-token"},
        }
        client = OpenMetadataClient(cfg, client=fake)

        rows, cursor = await client.list_tables(after="prev", limit=2)

        assert rows == [{"name": "t1"}, {"name": "t2"}]
        assert cursor == "next-token"
        assert fake.calls[0]["params"] == {"after": "prev", "limit": 2}

    async def test_list_dashboards_targets_dashboards_url(self) -> None:
        fake = FakeHttpx()
        cfg = OpenMetadataConfig(
            host_url="https://om.acme.com", jwt_token="jwt"
        )
        fake.responses[
            ("GET", "https://om.acme.com/api/v1/dashboards")
        ] = {"data": [{"name": "d1"}], "paging": {}}
        client = OpenMetadataClient(cfg, client=fake)

        rows, cursor = await client.list_dashboards()

        assert rows == [{"name": "d1"}]
        assert cursor is None
        assert fake.calls[0]["url"].endswith("/api/v1/dashboards")


class TestFetchPage(unittest.IsolatedAsyncioTestCase):
    async def test_uses_configured_entity_type(self) -> None:
        fake = FakeHttpx()
        cfg = OpenMetadataConfig(
            host_url="https://om.acme.com", jwt_token="jwt"
        )
        fake.responses[
            ("GET", "https://om.acme.com/api/v1/tables")
        ] = {"data": [{"id": 1}], "paging": {"after": "x"}}
        client = OpenMetadataClient(cfg, client=fake)

        rows, cursor = await client.fetch_page(
            cursor="prev", page_size=10
        )

        assert rows == [{"id": 1}]
        assert cursor == "x"
        assert fake.calls[0]["params"] == {"after": "prev", "limit": 10}

    async def test_no_paging_after_returns_none_cursor(self) -> None:
        fake = FakeHttpx()
        cfg = OpenMetadataConfig(
            host_url="https://om.acme.com", jwt_token="jwt"
        )
        fake.responses[
            ("GET", "https://om.acme.com/api/v1/tables")
        ] = {"data": [{"id": 1}], "paging": {}}
        client = OpenMetadataClient(cfg, client=fake)

        _, cursor = await client.fetch_page()

        assert cursor is None


class TestListEntities(unittest.IsolatedAsyncioTestCase):
    async def test_paginates_internally(self) -> None:
        fake = FakeHttpx()
        cfg = OpenMetadataConfig(
            host_url="https://om.acme.com", jwt_token="jwt"
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
                    {
                        "data": [{"name": "t1"}],
                        "paging": {"after": "tok2"},
                    }
                )
            return _FakeJson(
                {"data": [{"name": "t2"}], "paging": {}}
            )

        fake.request = request_request  # type: ignore[assignment]
        client = OpenMetadataClient(cfg, client=fake)

        results = []
        async for entity in client.list_entities("tables"):
            results.append(entity)

        assert results == [{"name": "t1"}, {"name": "t2"}]
        assert page_calls["count"] == 2

    async def test_filter_applied(self) -> None:
        fake = FakeHttpx()
        cfg = OpenMetadataConfig(
            host_url="https://om.acme.com", jwt_token="jwt"
        )
        fake.responses[
            ("GET", "https://om.acme.com/api/v1/tables")
        ] = {
            "data": [
                {"name": "t1", "tier": "gold"},
                {"name": "t2", "tier": "bronze"},
            ],
            "paging": {},
        }
        client = OpenMetadataClient(cfg, client=fake)

        results = []
        async for entity in client.list_entities(
            "tables", filter={"tier": "gold"}
        ):
            results.append(entity)

        assert results == [{"name": "t1", "tier": "gold"}]


class TestDescribeEntity(unittest.IsolatedAsyncioTestCase):
    async def test_calls_entities_endpoint(self) -> None:
        fake = FakeHttpx()
        cfg = OpenMetadataConfig(
            host_url="https://om.acme.com", jwt_token="jwt"
        )
        fake.responses[
            ("GET", "https://om.acme.com/api/v1/entities/abc-123")
        ] = {"id": "abc-123", "name": "thing"}
        client = OpenMetadataClient(cfg, client=fake)

        result = await client.describe_entity("abc-123")

        assert result == {"id": "abc-123", "name": "thing"}


class _FakeJson:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def json(self) -> Any:
        return self._payload
