"""Unit tests for :class:`AirbyteClient`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.connectors.api_client import ApiClient
from pirn.connectors.bi_catalog.airbyte_client import AirbyteClient
from pirn.connectors.bi_catalog.airbyte_config import AirbyteConfig
from pirn.connectors.capabilities.table_source import TableSource
from pirn.exceptions.connector_config_error import ConnectorConfigError


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


class _FakeHttpxWithHeaders(FakeHttpx):
    """``FakeHttpx`` plus the mutable ``headers`` mapping httpx clients expose."""

    def __init__(self) -> None:
        super().__init__()
        self.headers: dict[str, str] = {}


class _ClientBuildingAirbyteClient(AirbyteClient):
    """Builds a fake instead of a real ``httpx.AsyncClient``, so ``_create_client`` runs.

    ``client=`` short-circuits ``_create_client`` entirely, so the token
    exchange can only be exercised by faking the one seam that reaches httpx.
    """

    def __init__(self, config: AirbyteConfig, fake: _FakeHttpxWithHeaders) -> None:
        super().__init__(config)
        self._fake = fake

    def _build_httpx_client(self, extra: str, *, scrub_errors: bool = False, **_: Any) -> Any:
        return self._fake


class TestClientCredentialsExchange(unittest.IsolatedAsyncioTestCase):
    """The OAuth2 client-credentials grant ``AirbyteConfig`` documents, implemented."""

    @staticmethod
    def _client(
        **config_kwargs: Any,
    ) -> tuple[_ClientBuildingAirbyteClient, _FakeHttpxWithHeaders]:
        fake = _FakeHttpxWithHeaders()
        cfg = AirbyteConfig(base_url="https://api.airbyte.com/v1", **config_kwargs)
        return _ClientBuildingAirbyteClient(cfg, fake), fake

    async def test_client_id_and_secret_are_exchanged_for_a_bearer_token(self) -> None:
        client, fake = self._client(client_id="cid", client_secret="sec")
        fake.responses[("POST", "https://api.airbyte.com/v1/applications/token")] = {
            "access_token": "exchanged-tok"
        }
        fake.responses[("POST", "https://api.airbyte.com/v1/connections/list")] = {"data": []}

        await client.fetch_page()

        grant = fake.calls[0]
        assert grant["method"] == "POST"
        assert grant["url"] == "https://api.airbyte.com/v1/applications/token"
        assert grant["json"] == {
            "grant_type": "client_credentials",
            "client_id": "cid",
            "client_secret": "sec",
        }
        assert fake.headers["Authorization"] == "Bearer exchanged-tok"

    async def test_the_grant_is_sent_before_the_authorization_header_is_set(self) -> None:
        """A client-credentials grant must not carry a bearer token it does not have."""
        client, fake = self._client(client_id="cid", client_secret="sec")
        fake.responses[("POST", "https://api.airbyte.com/v1/applications/token")] = {
            "access_token": "exchanged-tok"
        }

        await client._ensure_client()

        assert fake.calls[0]["headers"] is None

    async def test_the_exchange_happens_once_and_is_pooled(self) -> None:
        client, fake = self._client(client_id="cid", client_secret="sec")
        fake.responses[("POST", "https://api.airbyte.com/v1/applications/token")] = {
            "access_token": "exchanged-tok"
        }
        fake.responses[("POST", "https://api.airbyte.com/v1/connections/list")] = {"data": []}

        await client.fetch_page()
        await client.fetch_page()

        grants = [c for c in fake.calls if c["url"].endswith("/applications/token")]
        assert len(grants) == 1

    async def test_an_explicit_access_token_skips_the_exchange(self) -> None:
        client, fake = self._client(access_token="direct-tok")

        await client._ensure_client()

        assert fake.calls == []
        assert fake.headers["Authorization"] == "Bearer direct-tok"

    async def test_neither_a_token_nor_a_full_credential_pair_is_refused(self) -> None:
        client, _ = self._client(client_id="cid")
        with self.assertRaisesRegex(ConnectorConfigError, "client_secret"):
            await client._ensure_client()

    async def test_no_credentials_at_all_is_refused(self) -> None:
        client, _ = self._client()
        with self.assertRaisesRegex(ConnectorConfigError, "access_token"):
            await client._ensure_client()

    async def test_a_grant_response_without_a_token_is_refused(self) -> None:
        client, fake = self._client(client_id="cid", client_secret="sec")
        fake.responses[("POST", "https://api.airbyte.com/v1/applications/token")] = {
            "error": "invalid_client"
        }
        with self.assertRaisesRegex(ConnectorConfigError, "no 'access_token'"):
            await client._ensure_client()


class _StandaloneTests(unittest.TestCase):
    def test_implements_api_client(self) -> None:
        client = AirbyteClient(client=FakeHttpx())
        assert isinstance(client, ApiClient)

    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            AirbyteClient()

    def test_sensitive_fields_listed(self) -> None:
        assert AirbyteConfig.sensitive_fields == ("client_secret", "access_token")


class TestRequest(unittest.IsolatedAsyncioTestCase):
    async def test_request_builds_full_url_and_returns_json(self) -> None:
        fake = FakeHttpx()
        cfg = AirbyteConfig(
            base_url="https://api.airbyte.com/v1",
            access_token="tok",
        )
        fake.responses[("GET", "https://api.airbyte.com/v1/sources")] = {"sources": []}
        client = AirbyteClient(cfg, client=fake)

        result = await client.request("GET", "/sources", params={"a": 1})

        assert result == {"sources": []}
        assert fake.calls == [
            {
                "method": "GET",
                "url": "https://api.airbyte.com/v1/sources",
                "params": {"a": 1},
                "json": None,
                "headers": None,
            }
        ]

    async def test_request_post_with_body(self) -> None:
        fake = FakeHttpx()
        client = AirbyteClient(AirbyteConfig(access_token="tok"), client=fake)

        await client.request("POST", "/sources", body={"name": "s3"})

        assert fake.calls[0]["method"] == "POST"
        assert fake.calls[0]["json"] == {"name": "s3"}


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_underlying_client(self) -> None:
        fake = FakeHttpx()
        client = AirbyteClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = AirbyteClient(client=FakeHttpx())
        await client.close()
        await client.close()

    async def test_request_after_close_raises(self) -> None:
        client = AirbyteClient(client=FakeHttpx())
        await client.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await client.request("GET", "/sources")

    def test_implements_table_source(self) -> None:
        client = AirbyteClient(client=FakeHttpx())
        assert isinstance(client, TableSource)

    def test_default_resource_is_connections(self) -> None:
        client = AirbyteClient(client=FakeHttpx())
        assert client.resource == "connections"

    def test_blank_resource_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "resource"):
            AirbyteClient(client=FakeHttpx(), resource="")


class TestFetchPage(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_page_posts_to_list_endpoint(self) -> None:
        fake = FakeHttpx()
        cfg = AirbyteConfig(
            base_url="https://api.airbyte.com",
            access_token="tok",
        )
        fake.responses[("POST", "https://api.airbyte.com/v1/connections/list")] = {
            "data": [{"id": "c1"}, {"id": "c2"}],
            "next_cursor": "next-tok",
        }
        client = AirbyteClient(cfg, client=fake)

        rows, cursor = await client.fetch_page(cursor="prev-tok", page_size=20)

        assert rows == [{"id": "c1"}, {"id": "c2"}]
        assert cursor == "next-tok"
        assert fake.calls[0]["method"] == "POST"
        assert fake.calls[0]["json"] == {
            "limit": 20,
            "cursor": "prev-tok",
        }

    async def test_fetch_page_no_next_cursor_returns_none(self) -> None:
        fake = FakeHttpx()
        cfg = AirbyteConfig(base_url="https://api.airbyte.com", access_token="tok")
        fake.responses[("POST", "https://api.airbyte.com/v1/connections/list")] = {
            "data": [{"id": "c1"}]
        }
        client = AirbyteClient(cfg, client=fake)

        _, cursor = await client.fetch_page()

        assert cursor is None


class TestVendorTypedListings(unittest.IsolatedAsyncioTestCase):
    async def test_list_connections(self) -> None:
        fake = FakeHttpx()
        cfg = AirbyteConfig(base_url="https://api.airbyte.com", access_token="tok")
        fake.responses[("POST", "https://api.airbyte.com/v1/connections/list")] = {
            "data": [{"id": "c1"}]
        }
        client = AirbyteClient(cfg, client=fake)

        rows, _ = await client.list_connections(limit=5)

        assert rows == [{"id": "c1"}]
        assert fake.calls[0]["url"].endswith("/v1/connections/list")
        assert fake.calls[0]["json"] == {"limit": 5}

    async def test_list_workspaces(self) -> None:
        fake = FakeHttpx()
        cfg = AirbyteConfig(base_url="https://api.airbyte.com", access_token="tok")
        fake.responses[("POST", "https://api.airbyte.com/v1/workspaces/list")] = {
            "data": [{"id": "w1"}]
        }
        client = AirbyteClient(cfg, client=fake)

        rows, _ = await client.list_workspaces()

        assert rows == [{"id": "w1"}]
        assert fake.calls[0]["url"].endswith("/v1/workspaces/list")
