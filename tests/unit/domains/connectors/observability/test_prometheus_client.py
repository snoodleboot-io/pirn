"""Unit tests for :class:`PrometheusClient`.

Uses an injected stub httpx-like async client. No real Prometheus
server needed.
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from typing import Any

from pirn.connectors.api_client import ApiClient
from pirn.connectors.capabilities.metric_query import MetricQuery
from pirn.connectors.observability.prometheus_client import (
    PrometheusClient,
)
from pirn.connectors.observability.prometheus_config import (
    PrometheusConfig,
)

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
        self.response: Any = {"status": "success", "data": {"result": []}}
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
        client = PrometheusClient(client=FakeHttpx())
        assert isinstance(client, ApiClient)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            PrometheusClient()
    
    
    def test_sensitive_fields_listed(self) -> None:
        assert PrometheusConfig.sensitive_fields == ("bearer_token",)
    
    
# ──────────────────────────────────────────────────────────── request


class TestRequest(unittest.IsolatedAsyncioTestCase):
    async def test_request_dispatches_query(self) -> None:
        fake = FakeHttpx()
        fake.response = {
            "status": "success",
            "data": {"resultType": "vector", "result": [{"value": 1}]},
        }
        client = PrometheusClient(client=fake)

        result = await client.request(
            "GET",
            "/api/v1/query",
            params={"query": "up"},
        )

        assert result == {
            "status": "success",
            "data": {"resultType": "vector", "result": [{"value": 1}]},
        }
        assert fake.calls == [
            (
                "GET",
                "/api/v1/query",
                {
                    "params": {"query": "up"},
                    "json": None,
                    "headers": None,
                },
            )
        ]

    async def test_request_returns_stub_response(self) -> None:
        fake = FakeHttpx()
        fake.response = {"status": "success", "data": {"result": [42]}}
        client = PrometheusClient(client=fake)

        result = await client.request("GET", "/api/v1/query", params={"query": "x"})

        assert result == {"status": "success", "data": {"result": [42]}}

    async def test_request_rejects_empty_method(self) -> None:
        client = PrometheusClient(client=FakeHttpx())
        with self.assertRaisesRegex(ValueError, "method"):
            await client.request("", "/api/v1/query")

    async def test_request_rejects_empty_path(self) -> None:
        client = PrometheusClient(client=FakeHttpx())
        with self.assertRaisesRegex(ValueError, "path"):
            await client.request("GET", "")


# ──────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_underlying_client(self) -> None:
        fake = FakeHttpx()
        client = PrometheusClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = PrometheusClient(client=FakeHttpx())
        await client.close()
        await client.close()

    async def test_request_after_close_raises(self) -> None:
        client = PrometheusClient(client=FakeHttpx())
        await client.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await client.request("GET", "/api/v1/query")


# ─────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_bearer_token(self) -> None:
        cfg = PrometheusConfig(
            base_url="http://prometheus:9090",
            bearer_token="prom-secret",
        )
        text = repr(cfg)
        assert "prom-secret" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_bearer_token(self) -> None:
        cfg = PrometheusConfig(
            base_url="http://prometheus:9090",
            bearer_token="prom-secret",
        )
        d = cfg.to_audit_dict()
        assert d["bearer_token"] == "<redacted>"
        assert d["base_url"] == "http://prometheus:9090"


# ──────────────────────────────────────────────────────── capabilities


    def test_implements_metric_query(self) -> None:
        client = PrometheusClient(client=FakeHttpx())
        assert isinstance(client, MetricQuery)
    
    
# ─────────────────────────────────────────────────── MetricQuery adapter


class TestQuery(unittest.IsolatedAsyncioTestCase):
    async def test_instant_query_when_start_omitted(self) -> None:
        fake = FakeHttpx()
        fake.response = {
            "status": "success",
            "data": {"resultType": "vector", "result": []},
        }
        client = PrometheusClient(client=fake)
        result = await client.query("up")
        assert result == fake.response
        method, path, opts = fake.calls[0]
        assert method == "GET"
        assert path == "/api/v1/query"
        assert opts["params"] == {"query": "up"}

    async def test_instant_query_with_time(self) -> None:
        fake = FakeHttpx()
        fake.response = {"status": "success", "data": {"result": []}}
        client = PrometheusClient(client=fake)
        ts = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
        await client.query_instant("up", time=ts)
        assert fake.calls[0][2]["params"] == {
            "query": "up",
            "time": int(ts.timestamp()),
        }

    async def test_range_query_when_start_provided(self) -> None:
        fake = FakeHttpx()
        fake.response = {
            "status": "success",
            "data": {"resultType": "matrix", "result": []},
        }
        client = PrometheusClient(client=fake)
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 1, 2, tzinfo=UTC)
        result = await client.query("up", start=start, end=end, step="30s")
        assert result == fake.response
        method, path, opts = fake.calls[0]
        assert method == "GET"
        assert path == "/api/v1/query_range"
        assert opts["params"] == {
            "query": "up",
            "start": int(start.timestamp()),
            "end": int(end.timestamp()),
            "step": "30s",
        }

    async def test_range_query_default_step(self) -> None:
        fake = FakeHttpx()
        fake.response = {"status": "success", "data": {"result": []}}
        client = PrometheusClient(client=fake)
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 1, 2, tzinfo=UTC)
        await client.query("up", start=start, end=end)
        assert fake.calls[0][2]["params"]["step"] == "60s"

    async def test_range_query_requires_end_when_start_set(self) -> None:
        client = PrometheusClient(client=FakeHttpx())
        with self.assertRaisesRegex(ValueError, "end is required"):
            await client.query(
                "up",
                start=datetime(2024, 1, 1, tzinfo=UTC),
            )

    async def test_query_rejects_empty(self) -> None:
        client = PrometheusClient(client=FakeHttpx())
        with self.assertRaisesRegex(ValueError, "query"):
            await client.query("")

    async def test_query_range_rejects_empty_step(self) -> None:
        client = PrometheusClient(client=FakeHttpx())
        with self.assertRaisesRegex(ValueError, "step"):
            await client.query_range(
                "up",
                start=datetime(2024, 1, 1, tzinfo=UTC),
                end=datetime(2024, 1, 2, tzinfo=UTC),
                step="",
            )
