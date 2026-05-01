"""Unit tests for :class:`DatadogClient`.

Uses an injected stub client that mirrors the ``call_api`` slice of
``datadog_api_client.ApiClient``.
"""

from __future__ import annotations

from typing import Any

import pytest

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.observability.datadog_client import DatadogClient
from pirn.domains.connectors.observability.datadog_config import DatadogConfig


# ──────────────────────────────────────────────────────────── fake client


class FakeDatadog:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.response: Any = {"status": "ok"}
        self.closed = False

    def call_api(
        self,
        method: str,
        path: str,
        *,
        query_params: Any = None,
        body: Any = None,
        header_params: Any = None,
    ) -> Any:
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


def test_implements_api_client() -> None:
    client = DatadogClient(client=FakeDatadog())
    assert isinstance(client, ApiClient)


def test_construction_requires_config_or_client() -> None:
    with pytest.raises(TypeError, match="config= or client="):
        DatadogClient()


def test_sensitive_fields_listed() -> None:
    assert DatadogConfig.sensitive_fields == ("api_key", "app_key")


# ──────────────────────────────────────────────────────────── request


@pytest.mark.asyncio
class TestRequest:
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
        with pytest.raises(ValueError, match="method"):
            await client.request("", "/api/v1/metrics")

    async def test_request_rejects_empty_path(self) -> None:
        client = DatadogClient(client=FakeDatadog())
        with pytest.raises(ValueError, match="path"):
            await client.request("GET", "")


# ──────────────────────────────────────────────────────────── lifecycle


@pytest.mark.asyncio
class TestLifecycle:
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
        with pytest.raises(RuntimeError, match="closed"):
            await client.request("GET", "/api/v1/metrics")


# ──────────────────────────────────────────────────────── credential safety


class TestCredentialSafety:
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
