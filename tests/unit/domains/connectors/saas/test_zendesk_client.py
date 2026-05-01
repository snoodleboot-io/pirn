"""Unit tests for :class:`ZendeskClient`.

Uses an injected stub client whose ``request(method, path, ...)``
mirrors the entry point :class:`ZendeskClient` prefers. Covers the
fallback path through ``users._call_api`` as well. No real Zendesk
account needed.
"""

from __future__ import annotations

from typing import Any

import pytest

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.saas.zendesk_client import ZendeskClient
from pirn.domains.connectors.saas.zendesk_config import ZendeskConfig


# ──────────────────────────────────────────────────────────── fake clients


class FakeZenpyTopLevel:
    """Stub exposing the preferred top-level ``request`` method."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Any, Any, Any]] = []
        self.response: Any = {"ok": True}
        self.closed = False

    def request(
        self,
        method: str,
        path: str,
        params: Any = None,
        body: Any = None,
        headers: Any = None,
    ) -> Any:
        self.calls.append((method, path, params, body, headers))
        return self.response

    def close(self) -> None:
        self.closed = True


class FakeUsers:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Any, Any]] = []
        self.response: Any = {"users": []}

    def _call_api(
        self,
        method: str,
        path: str,
        params: Any = None,
        body: Any = None,
    ) -> Any:
        self.calls.append((method, path, params, body))
        return self.response


class FakeZenpyFallback:
    """Stub without top-level ``request`` — exercises the fallback."""

    def __init__(self) -> None:
        self.users = FakeUsers()
        self.closed = False

    def close(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── conformance


def test_implements_api_client() -> None:
    client = ZendeskClient(client=FakeZenpyTopLevel())
    assert isinstance(client, ApiClient)


def test_construction_requires_config_or_client() -> None:
    with pytest.raises(TypeError, match="config= or client="):
        ZendeskClient()


def test_sensitive_fields_listed() -> None:
    assert ZendeskConfig.sensitive_fields == ("api_token", "oauth_token")


# ────────────────────────────────────────────────────────────── dispatch


@pytest.mark.asyncio
class TestRequest:
    async def test_request_uses_top_level(self) -> None:
        fake = FakeZenpyTopLevel()
        client = ZendeskClient(client=fake)

        result = await client.request(
            "GET",
            "/api/v2/tickets/1.json",
            params={"include": "users"},
            headers={"Accept": "application/json"},
        )

        assert result == {"ok": True}
        assert fake.calls == [
            (
                "GET",
                "/api/v2/tickets/1.json",
                {"include": "users"},
                None,
                {"Accept": "application/json"},
            )
        ]

    async def test_request_falls_back_to_call_api(self) -> None:
        fake = FakeZenpyFallback()
        client = ZendeskClient(client=fake)

        result = await client.request(
            "POST",
            "/api/v2/tickets.json",
            body={"ticket": {"subject": "hi"}},
        )

        assert result == {"users": []}
        assert fake.users.calls == [
            (
                "POST",
                "/api/v2/tickets.json",
                None,
                {"ticket": {"subject": "hi"}},
            )
        ]


# ─────────────────────────────────────────────────────────────── lifecycle


@pytest.mark.asyncio
class TestLifecycle:
    async def test_close_closes_underlying_client(self) -> None:
        fake = FakeZenpyTopLevel()
        client = ZendeskClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = ZendeskClient(client=FakeZenpyTopLevel())
        await client.close()
        await client.close()

    async def test_request_after_close_raises(self) -> None:
        client = ZendeskClient(client=FakeZenpyTopLevel())
        await client.close()
        with pytest.raises(RuntimeError, match="closed"):
            await client.request("GET", "/api/v2/tickets.json")


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety:
    def test_repr_redacts_api_token(self) -> None:
        cfg = ZendeskConfig(
            subdomain="acme",
            email="agent@acme.com",
            api_token="secret-leaks",
        )
        text = repr(cfg)
        assert "secret-leaks" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_oauth_token(self) -> None:
        cfg = ZendeskConfig(
            subdomain="acme",
            email="agent@acme.com",
            oauth_token="bearer-leaks",
        )
        d = cfg.to_audit_dict()
        assert d["oauth_token"] == "<redacted>"
        assert d["subdomain"] == "acme"
