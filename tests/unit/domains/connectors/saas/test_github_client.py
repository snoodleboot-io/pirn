"""Unit tests for :class:`GitHubClient`.

Uses an injected stub client that mirrors PyGithub's
``Github.requester.requestJsonAndCheck`` slice. No real GitHub access
needed.
"""

from __future__ import annotations

from typing import Any

import pytest

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.saas.github_client import GitHubClient
from pirn.domains.connectors.saas.github_config import GitHubConfig


# ──────────────────────────────────────────────────────────── fake client


class FakeRequester:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Any, Any, Any]] = []
        self.response: Any = ({"X-Stub": "1"}, {"ok": True})

    def requestJsonAndCheck(
        self,
        method: str,
        url: str,
        parameters: Any,
        headers: Any,
        input: Any,
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


def test_implements_api_client() -> None:
    client = GitHubClient(client=FakeGithubClient())
    assert isinstance(client, ApiClient)


def test_construction_requires_config_or_client() -> None:
    with pytest.raises(TypeError, match="config= or client="):
        GitHubClient()


def test_sensitive_fields_listed() -> None:
    assert GitHubConfig.sensitive_fields == ("token", "private_key")


# ────────────────────────────────────────────────────────────── dispatch


@pytest.mark.asyncio
class TestRequest:
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


@pytest.mark.asyncio
class TestLifecycle:
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
        with pytest.raises(RuntimeError, match="closed"):
            await client.request("GET", "/user")


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety:
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
