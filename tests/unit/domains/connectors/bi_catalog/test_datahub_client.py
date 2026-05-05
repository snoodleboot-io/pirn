"""Unit tests for :class:`DataHubClient`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.bi_catalog.datahub_client import DataHubClient
from pirn.domains.connectors.bi_catalog.datahub_config import DataHubConfig
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
        client = DataHubClient(client=FakeHttpx())
        assert isinstance(client, ApiClient)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            DataHubClient()
    
    
    def test_sensitive_fields_listed(self) -> None:
        assert DataHubConfig.sensitive_fields == ("token",)
    
    
class TestRequest(unittest.IsolatedAsyncioTestCase):
    async def test_request_builds_full_url_and_returns_json(self) -> None:
        fake = FakeHttpx()
        cfg = DataHubConfig(
            gms_url="https://gms.acme.com", token="tok"
        )
        fake.responses[
            ("GET", "https://gms.acme.com/entities")
        ] = {"entities": [{"urn": "urn:foo"}]}
        client = DataHubClient(cfg, client=fake)

        result = await client.request(
            "GET", "/entities", params={"a": 1}
        )

        assert result == {"entities": [{"urn": "urn:foo"}]}
        assert fake.calls == [
            {
                "method": "GET",
                "url": "https://gms.acme.com/entities",
                "params": {"a": 1},
                "json": None,
                "headers": None,
            }
        ]

    async def test_request_graphql_post(self) -> None:
        fake = FakeHttpx()
        cfg = DataHubConfig(gms_url="https://gms.acme.com")
        client = DataHubClient(cfg, client=fake)

        await client.request(
            "POST",
            "/api/graphql",
            body={"query": "{ me { username } }"},
        )

        assert fake.calls[0]["method"] == "POST"
        assert fake.calls[0]["url"] == "https://gms.acme.com/api/graphql"
        assert fake.calls[0]["json"] == {"query": "{ me { username } }"}


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_underlying_client(self) -> None:
        fake = FakeHttpx()
        client = DataHubClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = DataHubClient(client=FakeHttpx())
        await client.close()
        await client.close()

    async def test_request_after_close_raises(self) -> None:
        client = DataHubClient(client=FakeHttpx())
        await client.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await client.request("GET", "/entities")


    def test_implements_table_source_and_metadata_catalog(self) -> None:
        client = DataHubClient(client=FakeHttpx())
        assert isinstance(client, TableSource)
        assert isinstance(client, MetadataCatalog)
    
    
    def test_default_entity_type_is_dataset(self) -> None:
        client = DataHubClient(client=FakeHttpx())
        assert client.entity_type == "dataset"
    
    
    def test_blank_entity_type_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "entity_type"):
            DataHubClient(client=FakeHttpx(), entity_type="")
    
    
class TestSearchEntities(unittest.IsolatedAsyncioTestCase):
    async def test_returns_entities_and_next_cursor_when_more(self) -> None:
        fake = FakeHttpx()
        cfg = DataHubConfig(gms_url="https://gms.acme.com")
        fake.responses[("GET", "https://gms.acme.com/entities")] = {
            "entities": [{"urn": "urn:1"}, {"urn": "urn:2"}],
            "total": 5,
        }
        client = DataHubClient(cfg, client=fake)

        rows, cursor = await client.search_entities(
            "dataset", "*", start=0, count=2
        )

        assert rows == [{"urn": "urn:1"}, {"urn": "urn:2"}]
        assert cursor == "2"
        assert fake.calls[0]["params"] == {
            "entity": "dataset",
            "query": "*",
            "start": 0,
            "count": 2,
        }

    async def test_returns_none_cursor_at_end(self) -> None:
        fake = FakeHttpx()
        cfg = DataHubConfig(gms_url="https://gms.acme.com")
        fake.responses[("GET", "https://gms.acme.com/entities")] = {
            "entities": [{"urn": "urn:1"}],
            "total": 2,
        }
        client = DataHubClient(cfg, client=fake)

        rows, cursor = await client.search_entities(
            "dataset", "*", start=1, count=1
        )

        assert rows == [{"urn": "urn:1"}]
        assert cursor is None


class TestFetchPage(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_page_uses_configured_entity_type(self) -> None:
        fake = FakeHttpx()
        cfg = DataHubConfig(gms_url="https://gms.acme.com")
        fake.responses[("GET", "https://gms.acme.com/entities")] = {
            "entities": [{"urn": "urn:a"}],
            "total": 1,
        }
        client = DataHubClient(cfg, client=fake, entity_type="dashboard")

        rows, cursor = await client.fetch_page(page_size=10)

        assert rows == [{"urn": "urn:a"}]
        assert cursor is None
        assert fake.calls[0]["params"]["entity"] == "dashboard"
        assert fake.calls[0]["params"]["start"] == 0
        assert fake.calls[0]["params"]["count"] == 10

    async def test_fetch_page_parses_cursor_to_offset(self) -> None:
        fake = FakeHttpx()
        cfg = DataHubConfig(gms_url="https://gms.acme.com")
        fake.responses[("GET", "https://gms.acme.com/entities")] = {
            "entities": [],
            "total": 100,
        }
        client = DataHubClient(cfg, client=fake)

        await client.fetch_page(cursor="50", page_size=25)

        assert fake.calls[0]["params"]["start"] == 50
        assert fake.calls[0]["params"]["count"] == 25


class TestListEntities(unittest.IsolatedAsyncioTestCase):
    async def test_paginates_internally_until_cursor_none(self) -> None:
        fake = FakeHttpx()
        cfg = DataHubConfig(gms_url="https://gms.acme.com")
        # list_entities pages with count=100. Use total=150 so two
        # pages are required: first 100 entities, then 50.
        page_calls = {"count": 0}
        first_page = [{"urn": f"u{i}"} for i in range(100)]
        second_page = [{"urn": f"u{i}"} for i in range(100, 150)]

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
                    {"entities": first_page, "total": 150}
                )
            return _FakeJson(
                {"entities": second_page, "total": 150}
            )

        fake.request = request_request  # type: ignore[assignment]
        client = DataHubClient(cfg, client=fake)

        results = []
        async for entity in client.list_entities("dataset"):
            results.append(entity)

        assert len(results) == 150
        assert page_calls["count"] == 2
        assert fake.calls[0]["params"]["start"] == 0
        assert fake.calls[1]["params"]["start"] == 100

    async def test_filter_matches_key_value(self) -> None:
        fake = FakeHttpx()
        cfg = DataHubConfig(gms_url="https://gms.acme.com")
        fake.responses[("GET", "https://gms.acme.com/entities")] = {
            "entities": [
                {"urn": "u1", "platform": "snowflake"},
                {"urn": "u2", "platform": "bigquery"},
            ],
            "total": 2,
        }
        client = DataHubClient(cfg, client=fake)

        results = []
        async for entity in client.list_entities(
            "dataset", filter={"platform": "snowflake"}
        ):
            results.append(entity)

        assert results == [{"urn": "u1", "platform": "snowflake"}]


class TestDescribeEntity(unittest.IsolatedAsyncioTestCase):
    async def test_describe_calls_entity_get(self) -> None:
        fake = FakeHttpx()
        cfg = DataHubConfig(gms_url="https://gms.acme.com")
        fake.responses[
            ("GET", "https://gms.acme.com/entity/urn:foo")
        ] = {"urn": "urn:foo", "name": "foo"}
        client = DataHubClient(cfg, client=fake)

        result = await client.describe_entity("urn:foo")

        assert result == {"urn": "urn:foo", "name": "foo"}
        assert fake.calls[0]["url"] == "https://gms.acme.com/entity/urn:foo"


class _FakeJson:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def json(self) -> Any:
        return self._payload
