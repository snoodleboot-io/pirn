"""Unit tests for :class:`GrafanaClient`.

Uses an injected stub httpx-like async client. No real Grafana server
needed.
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from typing import Any

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.capabilities.metric_query import MetricQuery
from pirn.domains.connectors.capabilities.table_source import TableSource
from pirn.domains.connectors.observability.grafana_client import GrafanaClient
from pirn.domains.connectors.observability.grafana_config import GrafanaConfig

# ──────────────────────────────────────────────────────────── fake client


class FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:  # pragma: no cover - no-op
        return None

    def json(self) -> Any:
        return self._payload


class FakeHttpx:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.response: Any = {"id": 1}
        self.closed = False

    async def request(
        self, method: str, path: str, *, params: Any = None, json: Any = None, headers: Any = None,
    ) -> FakeResponse:
        self.calls.append(
            (
                method,
                path,
                {"params": params, "json": json, "headers": headers},
            )
        )
        return FakeResponse(self.response)

    async def aclose(self) -> None:
        self.closed = True


# ──────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_api_client(self) -> None:
        client = GrafanaClient(client=FakeHttpx())
        assert isinstance(client, ApiClient)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            GrafanaClient()
    
    
    def test_sensitive_fields_listed(self) -> None:
        assert GrafanaConfig.sensitive_fields == ("api_key",)
    
    
# ──────────────────────────────────────────────────────────── request


class TestRequest(unittest.IsolatedAsyncioTestCase):
    async def test_request_dispatches_get(self) -> None:
        fake = FakeHttpx()
        fake.response = [{"id": 1, "uid": "abc", "title": "Home"}]
        client = GrafanaClient(client=fake)

        result = await client.request(
            "GET",
            "/api/search",
            params={"type": "dash-db"},
        )

        assert result == [{"id": 1, "uid": "abc", "title": "Home"}]
        assert fake.calls == [
            (
                "GET",
                "/api/search",
                {
                    "params": {"type": "dash-db"},
                    "json": None,
                    "headers": None,
                },
            )
        ]

    async def test_request_dispatches_post_with_body(self) -> None:
        fake = FakeHttpx()
        fake.response = {"id": 2, "uid": "def"}
        client = GrafanaClient(client=fake)

        result = await client.request(
            "POST",
            "/api/dashboards/db",
            body={"dashboard": {"title": "test"}},
        )

        assert result == {"id": 2, "uid": "def"}
        assert fake.calls == [
            (
                "POST",
                "/api/dashboards/db",
                {
                    "params": None,
                    "json": {"dashboard": {"title": "test"}},
                    "headers": None,
                },
            )
        ]

    async def test_request_rejects_empty_method(self) -> None:
        client = GrafanaClient(client=FakeHttpx())
        with self.assertRaisesRegex(ValueError, "method"):
            await client.request("", "/api/search")

    async def test_request_rejects_empty_path(self) -> None:
        client = GrafanaClient(client=FakeHttpx())
        with self.assertRaisesRegex(ValueError, "path"):
            await client.request("GET", "")


# ──────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_underlying_client(self) -> None:
        fake = FakeHttpx()
        client = GrafanaClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = GrafanaClient(client=FakeHttpx())
        await client.close()
        await client.close()

    async def test_request_after_close_raises(self) -> None:
        client = GrafanaClient(client=FakeHttpx())
        await client.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await client.request("GET", "/api/search")


# ─────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_api_key(self) -> None:
        cfg = GrafanaConfig(
            base_url="https://grafana.acme.com",
            api_key="grafana-secret",
        )
        text = repr(cfg)
        assert "grafana-secret" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_api_key(self) -> None:
        cfg = GrafanaConfig(
            base_url="https://grafana.acme.com",
            api_key="grafana-secret",
        )
        d = cfg.to_audit_dict()
        assert d["api_key"] == "<redacted>"
        assert d["base_url"] == "https://grafana.acme.com"


# ──────────────────────────────────────────────────────── capabilities


    def test_implements_table_source(self) -> None:
        client = GrafanaClient(client=FakeHttpx())
        assert isinstance(client, TableSource)
    
    
    def test_implements_metric_query(self) -> None:
        client = GrafanaClient(client=FakeHttpx())
        assert isinstance(client, MetricQuery)
    
    
    def test_default_resource_is_dashboards(self) -> None:
        client = GrafanaClient(client=FakeHttpx())
        assert client.resource == "dashboards"
    
    
    def test_resource_must_be_supported(self) -> None:
        with self.assertRaisesRegex(ValueError, "resource"):
            GrafanaClient(client=FakeHttpx(), resource="bogus")
    
    
    def test_resource_rejects_empty_string(self) -> None:
        with self.assertRaisesRegex(ValueError, "resource"):
            GrafanaClient(client=FakeHttpx(), resource="")
    
    
# ─────────────────────────────────────────────────── TableSource adapter


class TestFetchPage(unittest.IsolatedAsyncioTestCase):
    async def test_dashboards_default(self) -> None:
        fake = FakeHttpx()
        fake.response = [
            {"id": 1, "uid": "a", "title": "One"},
            {"id": 2, "uid": "b", "title": "Two"},
        ]
        client = GrafanaClient(client=fake)
        rows, next_cursor = await client.fetch_page(page_size=2)
        assert rows == fake.response
        assert next_cursor == "2"
        method, path, opts = fake.calls[0]
        assert method == "GET"
        assert path == "/api/search"
        assert opts["params"] == {
            "type": "dash-db",
            "page": 1,
            "limit": 2,
        }

    async def test_dashboards_no_next_when_partial(self) -> None:
        fake = FakeHttpx()
        fake.response = [{"id": 1, "uid": "a", "title": "One"}]
        client = GrafanaClient(client=fake)
        rows, next_cursor = await client.fetch_page(page_size=2)
        assert rows == fake.response
        assert next_cursor is None

    async def test_folders_resource(self) -> None:
        fake = FakeHttpx()
        fake.response = [{"id": 10, "title": "F1"}]
        client = GrafanaClient(client=fake, resource="folders")
        rows, next_cursor = await client.fetch_page(page_size=10)
        assert rows == fake.response
        assert next_cursor is None
        assert fake.calls[0][1] == "/api/folders"

    async def test_datasources_resource_slices_client_side(self) -> None:
        fake = FakeHttpx()
        fake.response = [
            {"id": i, "name": f"ds-{i}"} for i in range(5)
        ]
        client = GrafanaClient(client=fake, resource="datasources")
        rows, next_cursor = await client.fetch_page(page_size=2)
        assert rows == fake.response[:2]
        assert next_cursor == "2"
        rows2, next_cursor2 = await client.fetch_page(
            cursor="2", page_size=2
        )
        assert rows2 == fake.response[2:4]
        assert next_cursor2 == "3"
        rows3, next_cursor3 = await client.fetch_page(
            cursor="3", page_size=2
        )
        assert rows3 == fake.response[4:]
        assert next_cursor3 is None

    async def test_invalid_cursor_raises(self) -> None:
        client = GrafanaClient(client=FakeHttpx())
        with self.assertRaisesRegex(ValueError, "invalid cursor"):
            await client.fetch_page(cursor="abc")


# ─────────────────────────────────────────── Vendor-typed list helpers


class TestVendorListHelpers(unittest.IsolatedAsyncioTestCase):
    async def test_list_dashboards_passes_params(self) -> None:
        fake = FakeHttpx()
        fake.response = [{"id": 1, "uid": "a"}]
        client = GrafanaClient(client=fake)
        rows, next_cursor = await client.list_dashboards(page=2, limit=50)
        assert rows == fake.response
        assert next_cursor is None
        assert fake.calls[0][2]["params"] == {
            "type": "dash-db",
            "page": 2,
            "limit": 50,
        }

    async def test_list_folders_passes_params(self) -> None:
        fake = FakeHttpx()
        fake.response = []
        client = GrafanaClient(client=fake)
        rows, next_cursor = await client.list_folders()
        assert rows == []
        assert next_cursor is None
        assert fake.calls[0][1] == "/api/folders"

    async def test_list_datasources_returns_all(self) -> None:
        fake = FakeHttpx()
        fake.response = [{"id": 1}, {"id": 2}]
        client = GrafanaClient(client=fake)
        rows, next_cursor = await client.list_datasources(limit=100)
        assert rows == [{"id": 1}, {"id": 2}]
        assert next_cursor is None
        assert fake.calls[0][1] == "/api/datasources"


# ─────────────────────────────────────────────────── MetricQuery adapter


class TestQuery(unittest.IsolatedAsyncioTestCase):
    async def test_query_requires_datasource_uid(self) -> None:
        client = GrafanaClient(client=FakeHttpx())
        with self.assertRaisesRegex(RuntimeError, "datasource_uid"):
            await client.query("up")

    async def test_query_rejects_empty(self) -> None:
        client = GrafanaClient(
            client=FakeHttpx(), datasource_uid="prom-uid"
        )
        with self.assertRaisesRegex(ValueError, "query"):
            await client.query("")

    async def test_query_posts_to_ds_query(self) -> None:
        fake = FakeHttpx()
        fake.response = {"results": {"A": {"frames": []}}}
        client = GrafanaClient(
            client=fake, datasource_uid="prom-uid"
        )
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 1, 2, tzinfo=UTC)
        result = await client.query("up", start=start, end=end, step="30s")
        assert result == fake.response
        method, path, opts = fake.calls[0]
        assert method == "POST"
        assert path == "/api/ds/query"
        body = opts["json"]
        assert body["from"] == str(int(start.timestamp() * 1000))
        assert body["to"] == str(int(end.timestamp() * 1000))
        assert body["queries"] == [
            {
                "refId": "A",
                "datasource": {"uid": "prom-uid"},
                "expr": "up",
                "interval": "30s",
            }
        ]

    async def test_query_without_window(self) -> None:
        fake = FakeHttpx()
        fake.response = {"results": {}}
        client = GrafanaClient(
            client=fake, datasource_uid="prom-uid"
        )
        await client.query("up")
        body = fake.calls[0][2]["json"]
        assert "from" not in body
        assert "to" not in body
        assert body["queries"][0]["expr"] == "up"
