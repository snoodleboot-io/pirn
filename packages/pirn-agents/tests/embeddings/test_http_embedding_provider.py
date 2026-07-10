"""Tests for :class:`HttpEmbeddingProvider` against a stub HTTP client double.

The adapter is exercised entirely offline via an injected stub client, so these
tests never import ``httpx``. Response ordering, batching over HTTP round-trips,
retry, and the missing-backend error path are all asserted.
"""

from __future__ import annotations

import sys
import unittest
from typing import Any

from pirn_agents.embeddings.http_embedding_provider import HttpEmbeddingProvider


class StubResponse:
    """A minimal ``httpx.Response`` double."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class StubHttpClient:
    """Records POSTs and returns embeddings sized to each input string."""

    def __init__(self, *, fail_times: int = 0, shuffle: bool = False) -> None:
        self.posts: list[dict[str, Any]] = []
        self.aclosed = False
        self._fail_times = fail_times
        self._shuffle = shuffle
        self._attempts = 0

    async def post(self, path: str, *, json: dict[str, Any]) -> StubResponse:
        self._attempts += 1
        if self._attempts <= self._fail_times:
            raise RuntimeError("boom")
        self.posts.append({"path": path, "json": json})
        rows = [
            {"embedding": [float(len(text)), 0.5], "index": index}
            for index, text in enumerate(json["input"])
        ]
        if self._shuffle:
            rows = list(reversed(rows))
        return StubResponse({"data": rows})

    async def aclose(self) -> None:
        self.aclosed = True


class TestHttpEmbeddingProvider(unittest.IsolatedAsyncioTestCase):
    def test_rejects_bad_credential(self) -> None:
        with self.assertRaises(TypeError):
            HttpEmbeddingProvider(
                base_url="http://x",
                model="m",
                credential="raw-secret",  # type: ignore[arg-type]
            )

    async def test_embeds_and_preserves_input_order(self) -> None:
        client = StubHttpClient(shuffle=True)
        provider = HttpEmbeddingProvider(
            base_url="http://svc/v1", model="m", client=client, batch_size=10
        )

        vectors = await provider.embed(["a", "bb", "ccc"])

        # despite the server returning rows reversed, output follows input order
        assert [vec[0] for vec in vectors] == [1.0, 2.0, 3.0]
        assert len(client.posts) == 1
        assert client.posts[0]["json"]["model"] == "m"

    async def test_batches_over_multiple_posts(self) -> None:
        client = StubHttpClient()
        provider = HttpEmbeddingProvider(
            base_url="http://svc", model="m", client=client, batch_size=2
        )

        await provider.embed(["a", "b", "c", "d", "e"])

        assert len(client.posts) == 3
        assert [len(p["json"]["input"]) for p in client.posts] == [2, 2, 1]

    async def test_retries_failed_post(self) -> None:
        client = StubHttpClient(fail_times=1)
        provider = HttpEmbeddingProvider(
            base_url="http://svc", model="m", client=client, batch_size=5, max_retries=2
        )

        vectors = await provider.embed(["a", "b"])

        assert len(vectors) == 2

    async def test_close_delegates_to_client_aclose(self) -> None:
        client = StubHttpClient()
        provider = HttpEmbeddingProvider(base_url="http://svc", model="m", client=client)
        await provider.embed(["a"])

        await provider.close()

        assert client.aclosed is True

    async def test_missing_httpx_raises_actionable_error(self) -> None:
        # No injected client and httpx absent -> friendly install error.
        assert "httpx" not in sys.modules
        provider = HttpEmbeddingProvider(base_url="http://svc", model="m")
        with self.assertRaises(ImportError) as ctx:
            await provider.embed(["a"])
        assert 'pip install "pirn-agents[web]"' in str(ctx.exception)


if __name__ == "__main__":
    unittest.main()
