"""Unit tests for :class:`HubSpotClient`.

Uses an injected stub client mirroring the ``hubspot.HubSpot.api_request``
surface. No real HubSpot account or network needed.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.capabilities.record_writer import RecordWriter
from pirn.domains.connectors.capabilities.table_source import TableSource
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



class _StandaloneTests(unittest.TestCase):
    def test_implements_api_client(self) -> None:
        client = HubSpotClient(client=FakeHubSpotClient())
        assert isinstance(client, ApiClient)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            HubSpotClient()
    
    
    def test_sensitive_fields_declared(self) -> None:
        cfg = HubSpotConfig()
        assert "access_token" in cfg.sensitive_fields
        assert "api_key" in cfg.sensitive_fields
    
    
# ────────────────────────────────────────────────────────── delegation


class TestRequest(unittest.IsolatedAsyncioTestCase):
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


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
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
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await client.request("GET", "/foo")


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_access_token_and_api_key(self) -> None:
        cfg = HubSpotConfig(
            access_token="pat-leaks",
            api_key="hapikey-leaks",
        )
        text = repr(cfg)
        assert "pat-leaks" not in text
        assert "hapikey-leaks" not in text
        assert "<redacted>" in text


# ───────────────────────────────────────────────────────── capability mixins


    def test_implements_table_source_and_record_writer(self) -> None:
        client = HubSpotClient(client=FakeHubSpotClient())
        assert isinstance(client, TableSource)
        assert isinstance(client, RecordWriter)
    
    
    def test_default_object_type_is_contacts(self) -> None:
        client = HubSpotClient(client=FakeHubSpotClient())
        assert client.object_type == "contacts"
    
    
    def test_construction_rejects_empty_object_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "object_type"):
            HubSpotClient(client=FakeHubSpotClient(), object_type="")
    
    
class TestFetchPage(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_page_initial_no_paging(self) -> None:
        fake = FakeHubSpotClient()
        fake.response = {"results": [{"id": "1"}, {"id": "2"}]}
        client = HubSpotClient(client=fake)
        rows, cursor = await client.fetch_page()
        assert rows == [{"id": "1"}, {"id": "2"}]
        assert cursor is None
        assert fake.calls[0]["method"] == "GET"
        assert fake.calls[0]["path"] == "/crm/v3/objects/contacts"

    async def test_fetch_page_returns_after_cursor(self) -> None:
        fake = FakeHubSpotClient()
        fake.response = {
            "results": [{"id": "1"}],
            "paging": {"next": {"after": "tok-42"}},
        }
        client = HubSpotClient(client=fake, object_type="companies")
        rows, cursor = await client.fetch_page(page_size=50)
        assert rows == [{"id": "1"}]
        assert cursor == "tok-42"
        assert fake.calls[0]["path"] == "/crm/v3/objects/companies"
        assert fake.calls[0]["qs"] == {"limit": 50}

    async def test_fetch_page_with_cursor_passes_after(self) -> None:
        fake = FakeHubSpotClient()
        fake.response = {"results": []}
        client = HubSpotClient(client=fake)
        await client.fetch_page("tok-7", page_size=25)
        assert fake.calls[0]["qs"] == {"after": "tok-7", "limit": 25}


class TestListObjects(unittest.IsolatedAsyncioTestCase):
    async def test_list_objects_passes_object_type(self) -> None:
        fake = FakeHubSpotClient()
        fake.response = {"results": [{"id": "x"}]}
        client = HubSpotClient(client=fake)
        rows, cursor = await client.list_objects("deals", limit=10)
        assert rows == [{"id": "x"}]
        assert cursor is None
        assert fake.calls[0]["path"] == "/crm/v3/objects/deals"
        assert fake.calls[0]["qs"] == {"limit": 10}

    async def test_list_objects_rejects_empty_type(self) -> None:
        client = HubSpotClient(client=FakeHubSpotClient())
        with self.assertRaisesRegex(ValueError, "object_type"):
            await client.list_objects("")


class TestWriteRecords(unittest.IsolatedAsyncioTestCase):
    async def test_write_records_posts_each_to_object_path(self) -> None:
        fake = FakeHubSpotClient()
        client = HubSpotClient(client=fake, object_type="contacts")
        count = await client.write_records(
            [
                {"properties": {"email": "a@b"}},
                {"properties": {"email": "c@d"}},
            ]
        )
        assert count == 2
        assert len(fake.calls) == 2
        assert fake.calls[0]["method"] == "POST"
        assert fake.calls[0]["path"] == "/crm/v3/objects/contacts"
        assert fake.calls[0]["body"] == {
            "properties": {"email": "a@b"}
        }

    async def test_write_records_empty_returns_zero(self) -> None:
        fake = FakeHubSpotClient()
        client = HubSpotClient(client=fake)
        count = await client.write_records([])
        assert count == 0
        assert fake.calls == []
