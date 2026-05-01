"""Unit tests for :class:`SalesforceClient`.

Uses an injected stub client mirroring ``simple_salesforce.Salesforce``'s
``query``/``restful``/``session`` surface. No real Salesforce org needed.
"""

from __future__ import annotations

from typing import Any

import pytest

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.saas.salesforce_client import SalesforceClient
from pirn.domains.connectors.saas.salesforce_config import SalesforceConfig


# ──────────────────────────────────────────────────────────── fake client


class FakeSalesforceSession:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeSalesforceClient:
    """Mirrors the surface ``SalesforceClient`` calls into."""

    def __init__(self) -> None:
        self.queries: list[str] = []
        self.restful_calls: list[dict[str, Any]] = []
        self.query_response: dict[str, Any] = {"records": [{"Id": "001"}]}
        self.restful_response: dict[str, Any] = {"ok": True}
        self.session = FakeSalesforceSession()

    def query(self, soql: str) -> dict[str, Any]:
        self.queries.append(soql)
        return self.query_response

    def restful(
        self,
        path: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.restful_calls.append(
            {"path": path, "method": method, "params": params, "json": json}
        )
        return self.restful_response


# ───────────────────────────────────────────────────────────── conformance


def test_implements_api_client() -> None:
    client = SalesforceClient(client=FakeSalesforceClient())
    assert isinstance(client, ApiClient)


def test_construction_requires_config_or_client() -> None:
    with pytest.raises(TypeError, match="config= or client="):
        SalesforceClient()


def test_sensitive_fields_declared() -> None:
    cfg = SalesforceConfig()
    assert "password" in cfg.sensitive_fields
    assert "security_token" in cfg.sensitive_fields
    assert "consumer_secret" in cfg.sensitive_fields


# ────────────────────────────────────────────────────────── delegation


@pytest.mark.asyncio
class TestRequest:
    async def test_rest_get_dispatches_to_restful(self) -> None:
        fake = FakeSalesforceClient()
        client = SalesforceClient(client=fake)
        result = await client.request(
            "GET", "/services/data/v59.0/sobjects/Account/001", params={"a": 1}
        )
        assert result == fake.restful_response
        assert fake.restful_calls == [
            {
                "path": "/services/data/v59.0/sobjects/Account/001",
                "method": "GET",
                "params": {"a": 1},
                "json": None,
            }
        ]

    async def test_post_passes_body(self) -> None:
        fake = FakeSalesforceClient()
        client = SalesforceClient(client=fake)
        result = await client.request(
            "POST",
            "/services/data/v59.0/sobjects/Account",
            body={"Name": "Acme"},
        )
        assert result == fake.restful_response
        assert fake.restful_calls[0]["method"] == "POST"
        assert fake.restful_calls[0]["json"] == {"Name": "Acme"}

    async def test_soql_get_dispatches_to_query(self) -> None:
        fake = FakeSalesforceClient()
        client = SalesforceClient(client=fake)
        result = await client.request(
            "GET", "/services/data/v59.0/query", params={"q": "SELECT Id FROM Account"}
        )
        assert result == fake.query_response
        assert fake.queries == ["SELECT Id FROM Account"]
        assert fake.restful_calls == []

    async def test_request_returns_stub_response(self) -> None:
        fake = FakeSalesforceClient()
        fake.restful_response = {"custom": "value"}
        client = SalesforceClient(client=fake)
        result = await client.request("GET", "/foo")
        assert result == {"custom": "value"}


# ─────────────────────────────────────────────────────────────── lifecycle


@pytest.mark.asyncio
class TestLifecycle:
    async def test_close_closes_session(self) -> None:
        fake = FakeSalesforceClient()
        client = SalesforceClient(client=fake)
        await client.close()
        assert fake.session.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = SalesforceClient(client=FakeSalesforceClient())
        await client.close()
        await client.close()

    async def test_request_after_close_raises(self) -> None:
        client = SalesforceClient(client=FakeSalesforceClient())
        await client.close()
        with pytest.raises(RuntimeError, match="closed"):
            await client.request("GET", "/foo")


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety:
    def test_repr_redacts_password_and_token(self) -> None:
        cfg = SalesforceConfig(
            username="alice",
            password="hunter2",
            security_token="topsecret-token",
            consumer_secret="oauth-shh",
        )
        text = repr(cfg)
        assert "hunter2" not in text
        assert "topsecret-token" not in text
        assert "oauth-shh" not in text
        assert "<redacted>" in text
