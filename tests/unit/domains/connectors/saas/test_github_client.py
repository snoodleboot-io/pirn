"""Unit tests for :class:`GitHubClient`.

Uses an injected stub client that mirrors PyGithub's
``Github.requester.requestJsonAndCheck`` slice. No real GitHub access
needed.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.capabilities.table_source import TableSource
from pirn.domains.connectors.saas.github_client import GitHubClient
from pirn.domains.connectors.saas.github_config import GitHubConfig

# ──────────────────────────────────────────────────────────── fake client


class FakeRequester:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Any, Any, Any]] = []
        self.response: Any = ({"X-Stub": "1"}, {"ok": True})

    def requestJsonAndCheck(
        self, method: str, url: str, parameters: Any, headers: Any, input: Any,
    ) -> Any:
        self.calls.append((method, url, parameters, headers, input))
        return self.response


class FakeGithubClient:
    """Mirrors the PyGithub surface ``GitHubClient`` calls into."""

    def __init__(self) -> None:
        self.requester = FakeRequester()
        self.closed = False

    def close(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_api_client(self) -> None:
        client = GitHubClient(client=FakeGithubClient())
        assert isinstance(client, ApiClient)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            GitHubClient()
    
    
    def test_sensitive_fields_listed(self) -> None:
        assert GitHubConfig.sensitive_fields == ("token", "private_key")
    
    
# ────────────────────────────────────────────────────────────── dispatch


class TestRequest(unittest.IsolatedAsyncioTestCase):
    async def test_request_forwards_to_requester(self) -> None:
        fake = FakeGithubClient()
        client = GitHubClient(client=fake)

        result = await client.request(
            "GET",
            "/user",
            params={"per_page": 10},
            headers={"Accept": "application/vnd.github+json"},
        )

        assert result == ({"X-Stub": "1"}, {"ok": True})
        assert len(fake.requester.calls) == 1
        method, url, parameters, headers, body = fake.requester.calls[0]
        assert method == "GET"
        assert url == "/user"
        assert parameters == {"per_page": 10}
        assert headers == {"Accept": "application/vnd.github+json"}
        assert body is None

    async def test_request_passes_body_for_post(self) -> None:
        fake = FakeGithubClient()
        client = GitHubClient(client=fake)

        await client.request(
            "POST",
            "/repos/o/r/issues",
            body={"title": "bug"},
        )

        _, _, parameters, _, body = fake.requester.calls[0]
        assert parameters is None
        assert body == {"title": "bug"}


# ─────────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_underlying_client(self) -> None:
        fake = FakeGithubClient()
        client = GitHubClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = GitHubClient(client=FakeGithubClient())
        await client.close()
        await client.close()

    async def test_request_after_close_raises(self) -> None:
        client = GitHubClient(client=FakeGithubClient())
        await client.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await client.request("GET", "/user")


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_token(self) -> None:
        cfg = GitHubConfig(token="ghp_secret-leaks")
        text = repr(cfg)
        assert "ghp_secret-leaks" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_private_key(self) -> None:
        cfg = GitHubConfig(
            app_id="123", private_key="-----BEGIN RSA PRIVATE KEY-----\nleak"
        )
        d = cfg.to_audit_dict()
        assert d["private_key"] == "<redacted>"
        assert d["app_id"] == "123"


# ────────────────────────────────────────────────────────── capability surface


    def test_implements_table_source(self) -> None:
        client = GitHubClient(client=FakeGithubClient())
        assert isinstance(client, TableSource)
    
    
    def test_construction_rejects_empty_resource(self) -> None:
        with self.assertRaisesRegex(ValueError, "resource must be a non-empty"):
            GitHubClient(client=FakeGithubClient(), resource="")
    
    
    def test_resource_property_defaults_to_issues(self) -> None:
        client = GitHubClient(client=FakeGithubClient())
        assert client.resource == "issues"
    
    
    def test_resource_property_reflects_constructor(self) -> None:
        client = GitHubClient(client=FakeGithubClient(), resource="repos")
        assert client.resource == "repos"
    
    
class TestVendorTypedReads(unittest.IsolatedAsyncioTestCase):
    async def test_list_repos_passes_owner_and_pagination(self) -> None:
        fake = FakeGithubClient()
        fake.requester.response = (
            {},
            [{"id": 1}, {"id": 2}, {"id": 3}],
        )
        client = GitHubClient(client=fake)

        rows, next_cursor = await client.list_repos(
            "octocat", page=1, per_page=3
        )

        assert rows == [{"id": 1}, {"id": 2}, {"id": 3}]
        assert next_cursor == "2"
        method, url, params, _, _ = fake.requester.calls[0]
        assert method == "GET"
        assert url == "/users/octocat/repos"
        assert params == {"page": 1, "per_page": 3}

    async def test_list_repos_partial_page_terminates(self) -> None:
        fake = FakeGithubClient()
        fake.requester.response = ({}, [{"id": 1}])
        client = GitHubClient(client=fake)

        rows, next_cursor = await client.list_repos(
            "octocat", page=4, per_page=10
        )

        assert rows == [{"id": 1}]
        assert next_cursor is None

    async def test_list_repos_empty_terminates(self) -> None:
        fake = FakeGithubClient()
        fake.requester.response = ({}, [])
        client = GitHubClient(client=fake)

        rows, next_cursor = await client.list_repos("octocat")

        assert rows == []
        assert next_cursor is None

    async def test_list_repos_rejects_empty_owner(self) -> None:
        client = GitHubClient(client=FakeGithubClient())
        with self.assertRaisesRegex(ValueError, "owner must be a non-empty"):
            await client.list_repos("")

    async def test_list_issues_targets_repo_path(self) -> None:
        fake = FakeGithubClient()
        fake.requester.response = ({}, [{"number": 1}, {"number": 2}])
        client = GitHubClient(client=fake)

        rows, next_cursor = await client.list_issues(
            "octocat", "spoon", page=1, per_page=2
        )

        assert rows == [{"number": 1}, {"number": 2}]
        assert next_cursor == "2"
        _, url, params, _, _ = fake.requester.calls[0]
        assert url == "/repos/octocat/spoon/issues"
        assert params == {"page": 1, "per_page": 2}

    async def test_list_issues_rejects_empty_args(self) -> None:
        client = GitHubClient(client=FakeGithubClient())
        with self.assertRaisesRegex(ValueError, "owner must be a non-empty"):
            await client.list_issues("", "spoon")
        with self.assertRaisesRegex(ValueError, "repo must be a non-empty"):
            await client.list_issues("octocat", "")


class TestFetchPage(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_page_pages_default_resource(self) -> None:
        fake = FakeGithubClient()
        fake.requester.response = ({}, [{"id": 1}, {"id": 2}])
        client = GitHubClient(client=fake)

        rows, next_cursor = await client.fetch_page(page_size=2)

        assert rows == [{"id": 1}, {"id": 2}]
        assert next_cursor == "2"
        _, url, params, _, _ = fake.requester.calls[0]
        assert url == "/issues"
        assert params == {"page": 1, "per_page": 2}

    async def test_fetch_page_uses_cursor(self) -> None:
        fake = FakeGithubClient()
        fake.requester.response = ({}, [{"id": 9}])
        client = GitHubClient(client=fake, resource="repos")

        rows, next_cursor = await client.fetch_page(
            cursor="3", page_size=1
        )

        assert rows == [{"id": 9}]
        assert next_cursor == "4"
        _, url, params, _, _ = fake.requester.calls[0]
        assert url == "/repos"
        assert params == {"page": 3, "per_page": 1}

    async def test_fetch_page_full_page_advances_cursor(self) -> None:
        fake = FakeGithubClient()
        fake.requester.response = ({}, [{"id": i} for i in range(30)])
        client = GitHubClient(client=fake)

        rows, next_cursor = await client.fetch_page()

        assert len(rows) == 30
        assert next_cursor == "2"

    async def test_fetch_page_empty_terminates(self) -> None:
        fake = FakeGithubClient()
        fake.requester.response = ({}, [])
        client = GitHubClient(client=fake)

        rows, next_cursor = await client.fetch_page(cursor="5")

        assert rows == []
        assert next_cursor is None
