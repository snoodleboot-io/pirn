"""Unit tests for :class:`ZendeskClient`.

Uses an injected stub client whose ``request(method, path, ...)``
mirrors the entry point :class:`ZendeskClient` prefers. Covers the
fallback path through ``users._call_api`` as well. No real Zendesk
account needed.
"""

from __future__ import annotations

from typing import Any
import unittest


from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.capabilities.record_writer import RecordWriter
from pirn.domains.connectors.capabilities.table_source import TableSource
from pirn.domains.connectors.saas.zendesk_client import ZendeskClient
from pirn.domains.connectors.saas.zendesk_config import ZendeskConfig


# ──────────────────────────────────────────────────────────── fake clients


class FakeZenpyTopLevel:
    """Stub exposing the preferred top-level ``request`` method."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Any, Any, Any]] = []
        self.response: Any = {"ok": True}
        self.closed = False

    def request(self, method: str, path: str, params: Any = None, body: Any = None, headers: Any = None,) -> Any:
        self.calls.append((method, path, params, body, headers))
        return self.response

    def close(self) -> None:
        self.closed = True


class FakeUsers:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Any, Any]] = []
        self.response: Any = {"users": []}

    def _call_api(self, method: str, path: str, params: Any = None, body: Any = None,) -> Any:
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



class _StandaloneTests(unittest.TestCase):
    def test_implements_api_client(self) -> None:
        client = ZendeskClient(client=FakeZenpyTopLevel())
        assert isinstance(client, ApiClient)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            ZendeskClient()
    
    
    def test_sensitive_fields_listed(self) -> None:
        assert ZendeskConfig.sensitive_fields == ("api_token", "oauth_token")
    
    
# ────────────────────────────────────────────────────────────── dispatch


class TestRequest(unittest.IsolatedAsyncioTestCase):
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


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
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
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await client.request("GET", "/api/v2/tickets.json")


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
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


# ───────────────────────────────────────────────────────── capability mixins


    def test_implements_table_source_and_record_writer(self) -> None:
        client = ZendeskClient(client=FakeZenpyTopLevel())
        assert isinstance(client, TableSource)
        assert isinstance(client, RecordWriter)
    
    
    def test_default_resource_is_tickets(self) -> None:
        client = ZendeskClient(client=FakeZenpyTopLevel())
        assert client.resource == "tickets"
    
    
    def test_construction_rejects_empty_resource(self) -> None:
        with self.assertRaisesRegex(ValueError, "resource"):
            ZendeskClient(client=FakeZenpyTopLevel(), resource="")
    
    
class TestFetchPage(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_page_initial_no_more(self) -> None:
        fake = FakeZenpyTopLevel()
        fake.response = {
            "tickets": [{"id": 1}, {"id": 2}],
            "meta": {"has_more": False, "after_cursor": None},
        }
        client = ZendeskClient(client=fake)
        rows, cursor = await client.fetch_page()
        assert rows == [{"id": 1}, {"id": 2}]
        assert cursor is None
        method, path, params, _, _ = fake.calls[0]
        assert method == "GET"
        assert path == "/api/v2/tickets.json"

    async def test_fetch_page_returns_after_cursor(self) -> None:
        fake = FakeZenpyTopLevel()
        fake.response = {
            "tickets": [{"id": 1}],
            "meta": {"has_more": True, "after_cursor": "abc-123"},
        }
        client = ZendeskClient(client=fake)
        rows, cursor = await client.fetch_page(page_size=50)
        assert rows == [{"id": 1}]
        assert cursor == "abc-123"
        _, _, params, _, _ = fake.calls[0]
        assert params == {"page[size]": 50}

    async def test_fetch_page_with_cursor_passes_after(self) -> None:
        fake = FakeZenpyTopLevel()
        fake.response = {
            "tickets": [],
            "meta": {"has_more": False},
        }
        client = ZendeskClient(client=fake)
        await client.fetch_page("abc-123", page_size=25)
        _, _, params, _, _ = fake.calls[0]
        assert params == {"page[after]": "abc-123", "page[size]": 25}

    async def test_fetch_page_uses_configured_resource(self) -> None:
        fake = FakeZenpyTopLevel()
        fake.response = {"users": [], "meta": {"has_more": False}}
        client = ZendeskClient(client=fake, resource="users")
        await client.fetch_page()
        _, path, _, _, _ = fake.calls[0]
        assert path == "/api/v2/users.json"


class TestVendorListShortcuts(unittest.IsolatedAsyncioTestCase):
    async def test_list_tickets(self) -> None:
        fake = FakeZenpyTopLevel()
        fake.response = {
            "tickets": [{"id": 9}],
            "meta": {"has_more": False},
        }
        client = ZendeskClient(client=fake)
        rows, cursor = await client.list_tickets()
        assert rows == [{"id": 9}]
        assert cursor is None
        _, path, _, _, _ = fake.calls[0]
        assert path == "/api/v2/tickets.json"

    async def test_list_users(self) -> None:
        fake = FakeZenpyTopLevel()
        fake.response = {
            "users": [{"id": 5}],
            "meta": {"has_more": False},
        }
        client = ZendeskClient(client=fake)
        rows, cursor = await client.list_users()
        assert rows == [{"id": 5}]
        assert cursor is None
        _, path, _, _, _ = fake.calls[0]
        assert path == "/api/v2/users.json"


class TestWriteRecords(unittest.IsolatedAsyncioTestCase):
    async def test_write_records_posts_each_ticket(self) -> None:
        fake = FakeZenpyTopLevel()
        client = ZendeskClient(client=fake)
        count = await client.write_records(
            [
                {"ticket": {"subject": "hi"}},
                {"ticket": {"subject": "bye"}},
            ]
        )
        assert count == 2
        assert len(fake.calls) == 2
        method, path, _, body, _ = fake.calls[0]
        assert method == "POST"
        assert path == "/api/v2/tickets.json"
        assert body == {"ticket": {"subject": "hi"}}

    async def test_write_records_empty_returns_zero(self) -> None:
        fake = FakeZenpyTopLevel()
        client = ZendeskClient(client=fake)
        count = await client.write_records([])
        assert count == 0
        assert fake.calls == []
