"""Unit tests for :class:`DataHubClient`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.bi_catalog.datahub_client import DataHubClient
from pirn.domains.connectors.bi_catalog.datahub_config import DataHubConfig


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
        return FakeResponse(self.responses.get((method, url), {"ok": True}))

    async def aclose(self) -> None:
        self.closed = True


def test_implements_api_client() -> None:
    client = DataHubClient(client=FakeHttpx())
    assert isinstance(client, ApiClient)


def test_construction_requires_config_or_client() -> None:
    with pytest.raises(TypeError, match="config= or client="):
        DataHubClient()


def test_sensitive_fields_listed() -> None:
    assert DataHubConfig.sensitive_fields == ("token",)


@pytest.mark.asyncio
class TestRequest:
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


@pytest.mark.asyncio
class TestLifecycle:
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
        with pytest.raises(RuntimeError, match="closed"):
            await client.request("GET", "/entities")
