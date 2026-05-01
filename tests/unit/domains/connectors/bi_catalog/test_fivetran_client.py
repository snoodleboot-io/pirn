"""Unit tests for :class:`FivetranClient`.

Uses an injected stub client whose ``request`` mirrors the slice of
``httpx.AsyncClient`` the connector calls. No real Fivetran account
needed.
"""

from __future__ import annotations

from typing import Any

import pytest

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.bi_catalog.fivetran_client import FivetranClient
from pirn.domains.connectors.bi_catalog.fivetran_config import FivetranConfig


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
        self,
        method: str,
        url: str,
        *,
        params: Any = None,
        json: Any = None,
        headers: Any = None,
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


def test_implements_api_client() -> None:
    client = FivetranClient(client=FakeHttpx())
    assert isinstance(client, ApiClient)


def test_construction_requires_config_or_client() -> None:
    with pytest.raises(TypeError, match="config= or client="):
        FivetranClient()


def test_sensitive_fields_listed() -> None:
    assert FivetranConfig.sensitive_fields == ("api_key", "api_secret")


# ────────────────────────────────────────────────────────────── dispatch


@pytest.mark.asyncio
class TestRequest:
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


@pytest.mark.asyncio
class TestLifecycle:
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
        with pytest.raises(RuntimeError, match="closed"):
            await client.request("GET", "/connectors")
