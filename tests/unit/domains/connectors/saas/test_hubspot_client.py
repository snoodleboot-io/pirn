"""Unit tests for :class:`HubSpotClient`.

Uses an injected stub client mirroring the ``hubspot.HubSpot.api_request``
surface. No real HubSpot account or network needed.
"""

from __future__ import annotations

from typing import Any

import pytest

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.saas.hubspot_client import HubSpotClient
from pirn.domains.connectors.saas.hubspot_config import HubSpotConfig


# ──────────────────────────────────────────────────────────── fake client


class FakeHubSpotClient:
    """Mirrors the ``api_request`` slice of the HubSpot SDK."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.response: dict[str, Any] = {"results": []}
        self.closed = False

    def api_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        return self.response

    def close(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── conformance


def test_implements_api_client() -> None:
    client = HubSpotClient(client=FakeHubSpotClient())
    assert isinstance(client, ApiClient)


def test_construction_requires_config_or_client() -> None:
    with pytest.raises(TypeError, match="config= or client="):
        HubSpotClient()


def test_sensitive_fields_declared() -> None:
    cfg = HubSpotConfig()
    assert "access_token" in cfg.sensitive_fields
    assert "api_key" in cfg.sensitive_fields


# ────────────────────────────────────────────────────────── delegation


@pytest.mark.asyncio
class TestRequest:
    async def test_get_dispatches_with_query_string(self) -> None:
        fake = FakeHubSpotClient()
        client = HubSpotClient(client=fake)
        result = await client.request(
            "GET", "/some/path", params={"a": 1}
        )
        assert result == fake.response
        assert fake.calls == [
            {"method": "GET", "path": "/some/path", "qs": {"a": 1}}
        ]

    async def test_post_passes_body(self) -> None:
        fake = FakeHubSpotClient()
        client = HubSpotClient(client=fake)
        await client.request(
            "POST", "/crm/v3/objects/contacts", body={"properties": {"email": "a@b"}}
        )
        assert fake.calls == [
            {
                "method": "POST",
                "path": "/crm/v3/objects/contacts",
                "body": {"properties": {"email": "a@b"}},
            }
        ]

    async def test_request_returns_stub_response(self) -> None:
        fake = FakeHubSpotClient()
        fake.response = {"ok": True}
        client = HubSpotClient(client=fake)
        result = await client.request("GET", "/foo")
        assert result == {"ok": True}


# ─────────────────────────────────────────────────────────────── lifecycle


@pytest.mark.asyncio
class TestLifecycle:
    async def test_close_closes_underlying_client(self) -> None:
        fake = FakeHubSpotClient()
        client = HubSpotClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = HubSpotClient(client=FakeHubSpotClient())
        await client.close()
        await client.close()

    async def test_request_after_close_raises(self) -> None:
        client = HubSpotClient(client=FakeHubSpotClient())
        await client.close()
        with pytest.raises(RuntimeError, match="closed"):
            await client.request("GET", "/foo")


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety:
    def test_repr_redacts_access_token_and_api_key(self) -> None:
        cfg = HubSpotConfig(
            access_token="pat-leaks",
            api_key="hapikey-leaks",
        )
        text = repr(cfg)
        assert "pat-leaks" not in text
        assert "hapikey-leaks" not in text
        assert "<redacted>" in text
