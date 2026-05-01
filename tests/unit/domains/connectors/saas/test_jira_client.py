"""Unit tests for :class:`JiraClient`.

Uses an injected stub client that mirrors the get/post/put/delete slice
of ``atlassian.Jira``. No real Jira account needed.
"""

from __future__ import annotations

from typing import Any

import pytest

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.capabilities.table_source import TableSource
from pirn.domains.connectors.saas.jira_client import JiraClient
from pirn.domains.connectors.saas.jira_config import JiraConfig


# ──────────────────────────────────────────────────────────── fake client


class FakeJira:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Any]] = []
        self.responses: dict[str, Any] = {}
        self.closed = False

    def get(self, path: str, params: Any = None) -> Any:
        self.calls.append(("GET", path, params))
        return self.responses.get(path, {"ok": True})

    def post(self, path: str, data: Any = None) -> Any:
        self.calls.append(("POST", path, data))
        return self.responses.get(path, {"ok": True})

    def put(self, path: str, data: Any = None) -> Any:
        self.calls.append(("PUT", path, data))
        return self.responses.get(path, {"ok": True})

    def delete(self, path: str) -> Any:
        self.calls.append(("DELETE", path, None))
        return self.responses.get(path, {"ok": True})

    def close(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── conformance


def test_implements_api_client() -> None:
    client = JiraClient(client=FakeJira())
    assert isinstance(client, ApiClient)


def test_construction_requires_config_or_client() -> None:
    with pytest.raises(TypeError, match="config= or client="):
        JiraClient()


def test_sensitive_fields_listed() -> None:
    assert JiraConfig.sensitive_fields == ("api_token",)


# ────────────────────────────────────────────────────────────── dispatch


@pytest.mark.asyncio
class TestRequest:
    async def test_request_dispatches_get(self) -> None:
        fake = FakeJira()
        fake.responses["/rest/api/3/issue/PIRN-1"] = {"key": "PIRN-1"}
        client = JiraClient(client=fake)

        result = await client.request(
            "GET", "/rest/api/3/issue/PIRN-1", params={"fields": "summary"}
        )

        assert result == {"key": "PIRN-1"}
        assert fake.calls == [
            ("GET", "/rest/api/3/issue/PIRN-1", {"fields": "summary"})
        ]

    async def test_request_dispatches_post(self) -> None:
        fake = FakeJira()
        client = JiraClient(client=fake)

        await client.request(
            "POST",
            "/rest/api/3/issue",
            body={"fields": {"summary": "bug"}},
        )

        assert fake.calls == [
            ("POST", "/rest/api/3/issue", {"fields": {"summary": "bug"}})
        ]

    async def test_request_dispatches_put(self) -> None:
        fake = FakeJira()
        client = JiraClient(client=fake)

        await client.request(
            "PUT",
            "/rest/api/3/issue/PIRN-1",
            body={"fields": {"summary": "fixed"}},
        )

        assert fake.calls == [
            (
                "PUT",
                "/rest/api/3/issue/PIRN-1",
                {"fields": {"summary": "fixed"}},
            )
        ]

    async def test_request_dispatches_delete(self) -> None:
        fake = FakeJira()
        client = JiraClient(client=fake)

        await client.request("DELETE", "/rest/api/3/issue/PIRN-1")

        assert fake.calls == [("DELETE", "/rest/api/3/issue/PIRN-1", None)]

    async def test_request_rejects_unknown_method(self) -> None:
        client = JiraClient(client=FakeJira())
        with pytest.raises(ValueError, match="unsupported HTTP method"):
            await client.request("PATCH", "/rest/api/3/issue/PIRN-1")


# ─────────────────────────────────────────────────────────────── lifecycle


@pytest.mark.asyncio
class TestLifecycle:
    async def test_close_closes_underlying_client(self) -> None:
        fake = FakeJira()
        client = JiraClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = JiraClient(client=FakeJira())
        await client.close()
        await client.close()

    async def test_request_after_close_raises(self) -> None:
        client = JiraClient(client=FakeJira())
        await client.close()
        with pytest.raises(RuntimeError, match="closed"):
            await client.request("GET", "/rest/api/3/myself")


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety:
    def test_repr_redacts_api_token(self) -> None:
        cfg = JiraConfig(
            url="https://acme.atlassian.net",
            username="alice@acme.com",
            api_token="secret-leaks",
        )
        text = repr(cfg)
        assert "secret-leaks" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_api_token(self) -> None:
        cfg = JiraConfig(
            url="https://acme.atlassian.net",
            username="alice@acme.com",
            api_token="secret-leaks",
        )
        d = cfg.to_audit_dict()
        assert d["api_token"] == "<redacted>"
        assert d["username"] == "alice@acme.com"


# ────────────────────────────────────────────────────────── capability surface


def test_implements_table_source() -> None:
    client = JiraClient(client=FakeJira())
    assert isinstance(client, TableSource)


def test_construction_rejects_empty_jql() -> None:
    with pytest.raises(ValueError, match="jql must be a non-empty"):
        JiraClient(client=FakeJira(), jql="")


def test_jql_property_defaults_to_none() -> None:
    client = JiraClient(client=FakeJira())
    assert client.jql is None


def test_jql_property_reflects_constructor() -> None:
    client = JiraClient(client=FakeJira(), jql="project=PIRN")
    assert client.jql == "project=PIRN"


@pytest.mark.asyncio
class TestSearch:
    async def test_search_passes_params_and_advances_cursor(self) -> None:
        fake = FakeJira()
        fake.responses["/search"] = {
            "issues": [{"key": "PIRN-1"}, {"key": "PIRN-2"}],
            "total": 10,
            "startAt": 0,
            "maxResults": 2,
        }
        client = JiraClient(client=fake)

        rows, next_cursor = await client.search(
            "project=PIRN", start_at=0, max_results=2
        )

        assert rows == [{"key": "PIRN-1"}, {"key": "PIRN-2"}]
        assert next_cursor == "2"
        method, path, params = fake.calls[0]
        assert method == "GET"
        assert path == "/search"
        assert params == {
            "jql": "project=PIRN",
            "startAt": 0,
            "maxResults": 2,
        }

    async def test_search_terminates_when_exhausted(self) -> None:
        fake = FakeJira()
        fake.responses["/search"] = {
            "issues": [{"key": "PIRN-9"}],
            "total": 5,
            "startAt": 4,
            "maxResults": 2,
        }
        client = JiraClient(client=fake)

        rows, next_cursor = await client.search(
            "project=PIRN", start_at=4, max_results=2
        )

        assert rows == [{"key": "PIRN-9"}]
        assert next_cursor is None

    async def test_search_rejects_empty_jql(self) -> None:
        client = JiraClient(client=FakeJira())
        with pytest.raises(ValueError, match="jql must be a non-empty"):
            await client.search("")


@pytest.mark.asyncio
class TestFetchPage:
    async def test_fetch_page_uses_constructor_jql(self) -> None:
        fake = FakeJira()
        fake.responses["/search"] = {
            "issues": [{"key": "PIRN-1"}],
            "total": 100,
            "startAt": 0,
            "maxResults": 50,
        }
        client = JiraClient(client=fake, jql="project=PIRN")

        rows, next_cursor = await client.fetch_page()

        assert rows == [{"key": "PIRN-1"}]
        assert next_cursor == "50"
        _, _, params = fake.calls[0]
        assert params == {
            "jql": "project=PIRN",
            "startAt": 0,
            "maxResults": 50,
        }

    async def test_fetch_page_advances_cursor(self) -> None:
        fake = FakeJira()
        fake.responses["/search"] = {
            "issues": [{"key": "PIRN-51"}],
            "total": 100,
            "startAt": 50,
            "maxResults": 50,
        }
        client = JiraClient(client=fake, jql="project=PIRN")

        rows, next_cursor = await client.fetch_page(cursor="50")

        assert rows == [{"key": "PIRN-51"}]
        assert next_cursor is None
        _, _, params = fake.calls[0]
        assert params["startAt"] == 50

    async def test_fetch_page_honours_page_size(self) -> None:
        fake = FakeJira()
        fake.responses["/search"] = {
            "issues": [],
            "total": 0,
            "startAt": 0,
            "maxResults": 25,
        }
        client = JiraClient(client=fake, jql="project=PIRN")

        await client.fetch_page(page_size=25)
        _, _, params = fake.calls[0]
        assert params["maxResults"] == 25

    async def test_fetch_page_without_jql_raises(self) -> None:
        client = JiraClient(client=FakeJira())
        with pytest.raises(RuntimeError, match="no jql configured"):
            await client.fetch_page()
