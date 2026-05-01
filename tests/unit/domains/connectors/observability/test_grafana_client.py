"""Unit tests for :class:`GrafanaClient`.

Uses an injected stub httpx-like async client. No real Grafana server
needed.
"""

from __future__ import annotations

from typing import Any

import pytest

from pirn.domains.connectors.api_client import ApiClient
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
        self,
        method: str,
        path: str,
        *,
        params: Any = None,
        json: Any = None,
        headers: Any = None,
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


def test_implements_api_client() -> None:
    client = GrafanaClient(client=FakeHttpx())
    assert isinstance(client, ApiClient)


def test_construction_requires_config_or_client() -> None:
    with pytest.raises(TypeError, match="config= or client="):
        GrafanaClient()


def test_sensitive_fields_listed() -> None:
    assert GrafanaConfig.sensitive_fields == ("api_key",)


# ──────────────────────────────────────────────────────────── request


@pytest.mark.asyncio
class TestRequest:
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
        with pytest.raises(ValueError, match="method"):
            await client.request("", "/api/search")

    async def test_request_rejects_empty_path(self) -> None:
        client = GrafanaClient(client=FakeHttpx())
        with pytest.raises(ValueError, match="path"):
            await client.request("GET", "")


# ──────────────────────────────────────────────────────────── lifecycle


@pytest.mark.asyncio
class TestLifecycle:
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
        with pytest.raises(RuntimeError, match="closed"):
            await client.request("GET", "/api/search")


# ─────────────────────────────────────────────────────── credential safety


class TestCredentialSafety:
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
