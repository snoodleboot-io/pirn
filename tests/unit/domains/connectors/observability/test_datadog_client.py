"""Unit tests for :class:`DatadogClient`.

Uses an injected stub client that mirrors the ``call_api`` slice of
``datadog_api_client.ApiClient``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import unittest


from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.capabilities.event_emitter import EventEmitter
from pirn.domains.connectors.capabilities.metric_query import MetricQuery
from pirn.domains.connectors.capabilities.table_source import TableSource
from pirn.domains.connectors.observability.datadog_client import DatadogClient
from pirn.domains.connectors.observability.datadog_config import DatadogConfig


# ──────────────────────────────────────────────────────────── fake client


class FakeDatadog:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.response: Any = {"status": "ok"}
        self.closed = False

    def call_api(self, method: str, path: str, *, query_params: Any = None, body: Any = None, header_params: Any = None,) -> Any:
        self.calls.append(
            (
                method,
                path,
                {
                    "query_params": query_params,
                    "body": body,
                    "header_params": header_params,
                },
            )
        )
        return self.response

    def close(self) -> None:
        self.closed = True


# ──────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_api_client(self) -> None:
        client = DatadogClient(client=FakeDatadog())
        assert isinstance(client, ApiClient)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            DatadogClient()
    
    
    def test_sensitive_fields_listed(self) -> None:
        assert DatadogConfig.sensitive_fields == ("api_key", "app_key")
    
    
# ──────────────────────────────────────────────────────────── request


class TestRequest(unittest.IsolatedAsyncioTestCase):
    async def test_request_dispatches_get(self) -> None:
        fake = FakeDatadog()
        fake.response = {"metrics": ["system.cpu.user"]}
        client = DatadogClient(client=fake)

        result = await client.request(
            "GET",
            "/api/v1/metrics",
            params={"from": "12345"},
        )

        assert result == {"metrics": ["system.cpu.user"]}
        assert fake.calls == [
            (
                "GET",
                "/api/v1/metrics",
                {
                    "query_params": {"from": "12345"},
                    "body": None,
                    "header_params": None,
                },
            )
        ]

    async def test_request_returns_stub_response(self) -> None:
        fake = FakeDatadog()
        fake.response = {"id": "abc"}
        client = DatadogClient(client=fake)

        result = await client.request("POST", "/api/v1/series", body={"a": 1})

        assert result == {"id": "abc"}

    async def test_request_rejects_empty_method(self) -> None:
        client = DatadogClient(client=FakeDatadog())
        with self.assertRaisesRegex(ValueError, "method"):
            await client.request("", "/api/v1/metrics")

    async def test_request_rejects_empty_path(self) -> None:
        client = DatadogClient(client=FakeDatadog())
        with self.assertRaisesRegex(ValueError, "path"):
            await client.request("GET", "")


# ──────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_underlying_client(self) -> None:
        fake = FakeDatadog()
        client = DatadogClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = DatadogClient(client=FakeDatadog())
        await client.close()
        await client.close()

    async def test_request_after_close_raises(self) -> None:
        client = DatadogClient(client=FakeDatadog())
        await client.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await client.request("GET", "/api/v1/metrics")


# ──────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_keys(self) -> None:
        cfg = DatadogConfig(
            api_key="dd-secret",
            app_key="app-secret",
            site="datadoghq.com",
        )
        text = repr(cfg)
        assert "dd-secret" not in text
        assert "app-secret" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_keys(self) -> None:
        cfg = DatadogConfig(
            api_key="dd-secret",
            app_key="app-secret",
        )
        d = cfg.to_audit_dict()
        assert d["api_key"] == "<redacted>"
        assert d["app_key"] == "<redacted>"
        assert d["site"] == "datadoghq.com"


# ──────────────────────────────────────────────────────── capabilities


    def test_implements_table_source(self) -> None:
        client = DatadogClient(client=FakeDatadog())
        assert isinstance(client, TableSource)
    
    
    def test_implements_event_emitter(self) -> None:
        client = DatadogClient(client=FakeDatadog())
        assert isinstance(client, EventEmitter)
    
    
    def test_implements_metric_query(self) -> None:
        client = DatadogClient(client=FakeDatadog())
        assert isinstance(client, MetricQuery)
    
    
    def test_default_resource_is_metrics(self) -> None:
        client = DatadogClient(client=FakeDatadog())
        assert client.resource == "metrics"
    
    
    def test_resource_must_be_non_empty(self) -> None:
        with self.assertRaisesRegex(ValueError, "resource"):
            DatadogClient(client=FakeDatadog(), resource="")
    
    
# ─────────────────────────────────────────────────── TableSource adapter


class TestFetchPage(unittest.IsolatedAsyncioTestCase):
    async def test_first_page_uses_zero_index(self) -> None:
        fake = FakeDatadog()
        fake.response = {
            "data": [{"id": "m1"}, {"id": "m2"}],
            "meta": {"page": {"has_more": True}},
        }
        client = DatadogClient(client=fake)
        rows, next_cursor = await client.fetch_page(page_size=2)
        assert rows == [{"id": "m1"}, {"id": "m2"}]
        assert next_cursor == "1"
        method, path, opts = fake.calls[0]
        assert method == "GET"
        assert path == "/api/v1/metrics"
        assert opts["query_params"] == {
            "page[number]": 0,
            "page[size]": 2,
        }

    async def test_cursor_advances_page_number(self) -> None:
        fake = FakeDatadog()
        fake.response = {
            "data": [{"id": "m3"}],
            "meta": {"page": {"has_more": False}},
        }
        client = DatadogClient(client=fake)
        rows, next_cursor = await client.fetch_page(cursor="2")
        assert rows == [{"id": "m3"}]
        assert next_cursor is None
        assert fake.calls[0][2]["query_params"]["page[number]"] == 2

    async def test_invalid_cursor_raises(self) -> None:
        client = DatadogClient(client=FakeDatadog())
        with self.assertRaisesRegex(ValueError, "invalid cursor"):
            await client.fetch_page(cursor="not-a-number")

    async def test_resource_routed_to_path(self) -> None:
        fake = FakeDatadog()
        fake.response = {"data": []}
        client = DatadogClient(client=fake, resource="events")
        await client.fetch_page()
        assert fake.calls[0][1] == "/api/v1/events"


# ─────────────────────────────────────────────────── EventEmitter adapter


class TestEmit(unittest.IsolatedAsyncioTestCase):
    async def test_emit_routes_to_submit_metric(self) -> None:
        fake = FakeDatadog()
        client = DatadogClient(client=fake)
        await client.emit(
            {
                "metric": "system.cpu.user",
                "points": [[1700000000, 0.42]],
                "tags": ["env:dev"],
            }
        )
        method, path, opts = fake.calls[0]
        assert method == "POST"
        assert path == "/api/v1/series"
        assert opts["body"] == {
            "series": [
                {
                    "metric": "system.cpu.user",
                    "points": [[1700000000, 0.42]],
                    "tags": ["env:dev"],
                }
            ]
        }

    async def test_emit_requires_metric_and_points(self) -> None:
        client = DatadogClient(client=FakeDatadog())
        with self.assertRaisesRegex(ValueError, "metric"):
            await client.emit({"points": []})
        with self.assertRaisesRegex(ValueError, "metric"):
            await client.emit({"metric": "x"})

    async def test_submit_metric_without_tags(self) -> None:
        fake = FakeDatadog()
        client = DatadogClient(client=fake)
        await client.submit_metric(
            "app.requests", [[1700000000, 1]],
        )
        body = fake.calls[0][2]["body"]
        assert body == {
            "series": [
                {"metric": "app.requests", "points": [[1700000000, 1]]}
            ]
        }

    async def test_submit_metric_rejects_empty_name(self) -> None:
        client = DatadogClient(client=FakeDatadog())
        with self.assertRaisesRegex(ValueError, "name"):
            await client.submit_metric("", [[1700000000, 1]])


# ─────────────────────────────────────────────────── MetricQuery adapter


class TestQuery(unittest.IsolatedAsyncioTestCase):
    async def test_query_converts_datetimes_to_timestamps(self) -> None:
        fake = FakeDatadog()
        fake.response = {"series": []}
        client = DatadogClient(client=fake)
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)
        result = await client.query(
            "avg:system.cpu.user{*}", start=start, end=end
        )
        assert result == {"series": []}
        method, path, opts = fake.calls[0]
        assert method == "GET"
        assert path == "/api/v1/query"
        assert opts["query_params"] == {
            "from": int(start.timestamp()),
            "to": int(end.timestamp()),
            "query": "avg:system.cpu.user{*}",
        }

    async def test_query_requires_start_and_end(self) -> None:
        client = DatadogClient(client=FakeDatadog())
        with self.assertRaisesRegex(ValueError, "start and end"):
            await client.query("system.cpu.user")

    async def test_query_rejects_empty_query(self) -> None:
        client = DatadogClient(client=FakeDatadog())
        with self.assertRaisesRegex(ValueError, "query"):
            await client.query(
                "",
                start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end=datetime(2024, 1, 2, tzinfo=timezone.utc),
            )

    async def test_query_metrics_passes_params(self) -> None:
        fake = FakeDatadog()
        fake.response = {"series": [{"name": "cpu"}]}
        client = DatadogClient(client=fake)
        start = datetime(2024, 6, 1, tzinfo=timezone.utc)
        end = datetime(2024, 6, 2, tzinfo=timezone.utc)
        result = await client.query_metrics(
            "system.cpu.user", start=start, end=end
        )
        assert result == {"series": [{"name": "cpu"}]}
