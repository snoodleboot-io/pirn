"""Tests for the source connectors (F25-S3): object store, web crawl, dedup.

Uses in-memory stub doubles for the F16 backends — a stub ``BlobStore`` and an
``HttpConnector`` wrapping a fake streaming client — so no real service or
network is touched. Covers happy path, content-hash dedup, and isolated
per-object failures (auth / rate limit).
"""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator, Sequence
from typing import Any

from pirn_agents.connectors.blob_store import BlobStore
from pirn_agents.connectors.http_connector import HttpConnector
from pirn_agents.specializations.document_processing.sources.content_hash_deduplicator import (
    ContentHashDeduplicator,
)
from pirn_agents.specializations.document_processing.sources.object_store_source_connector import (
    ObjectStoreSourceConnector,
)
from pirn_agents.specializations.document_processing.sources.web_crawl_source_connector import (
    WebCrawlSourceConnector,
)


class _StubBlobStore(BlobStore):
    """In-memory blob store; raises on keys listed in ``fail_keys``."""

    def __init__(self, objects: dict[str, bytes], *, fail_keys: Sequence[str] = ()) -> None:
        self._objects = dict(objects)
        self._fail = set(fail_keys)

    async def get(self, key: str) -> AsyncIterator[bytes]:
        if key in self._fail:
            raise RuntimeError("auth denied")
        yield self._objects[key]

    async def put(self, key: str, data: AsyncIterator[bytes]) -> None:
        self._objects[key] = b"".join([chunk async for chunk in data])

    async def list(self, prefix: str = "") -> Sequence[str]:
        return sorted(k for k in self._objects if k.startswith(prefix))


class _FakeStreamCtx:
    """Async context manager mimicking ``httpx``'s streaming response."""

    def __init__(self, payload: bytes | Exception) -> None:
        self._payload = payload

    async def __aenter__(self) -> _FakeStreamCtx:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    async def aiter_bytes(self) -> AsyncIterator[bytes]:
        assert isinstance(self._payload, bytes)
        yield self._payload


class _FakeHttpClient:
    """Fake httpx-compatible client mapping URL -> bytes or exception."""

    def __init__(self, responses: dict[str, bytes | Exception]) -> None:
        self._responses = responses

    def stream(self, _method: str, url: str, **_: Any) -> _FakeStreamCtx:
        return _FakeStreamCtx(self._responses[url])

    async def aclose(self) -> None:
        return None


def _http_connector(responses: dict[str, bytes | Exception]) -> HttpConnector:
    return HttpConnector(client=_FakeHttpClient(responses), egress_policy=lambda _url: None)


class TestContentHashDeduplicator(unittest.TestCase):
    def test_first_seen_is_new_then_duplicate(self) -> None:
        dedup = ContentHashDeduplicator()
        assert dedup.is_new(b"hello") is True
        assert dedup.is_new(b"hello") is False
        assert dedup.is_new(b"world") is True
        assert dedup.seen_count == 2

    def test_unknown_algorithm_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown hash algorithm"):
            ContentHashDeduplicator(algorithm="not-a-hash")


class TestObjectStoreSourceConnector(unittest.IsolatedAsyncioTestCase):
    async def test_yields_documents_with_hashes(self) -> None:
        store = _StubBlobStore({"docs/a.txt": b"alpha", "docs/b.txt": b"beta"})
        connector = ObjectStoreSourceConnector(blob_store=store, prefix="docs/")
        docs = [doc async for doc in connector.fetch()]
        assert [d.source_id for d in docs] == ["docs/a.txt", "docs/b.txt"]
        assert all(d.content_hash for d in docs)
        assert docs[0].metadata["source"] == "object_store"

    async def test_content_hash_dedup_skips_identical(self) -> None:
        store = _StubBlobStore({"a": b"same", "b": b"same", "c": b"other"})
        connector = ObjectStoreSourceConnector(blob_store=store)
        docs = [doc async for doc in connector.fetch()]
        assert {d.data for d in docs} == {b"same", b"other"}
        assert len(docs) == 2

    async def test_read_failure_recorded_not_raised(self) -> None:
        store = _StubBlobStore({"ok": b"x", "bad": b"y"}, fail_keys=["bad"])
        connector = ObjectStoreSourceConnector(blob_store=store)
        docs = [doc async for doc in connector.fetch()]
        assert [d.source_id for d in docs] == ["ok"]
        assert connector.errors == (("bad", "auth denied"),)

    def test_wrong_blob_store_type_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be a BlobStore"):
            ObjectStoreSourceConnector(blob_store=object())  # type: ignore[arg-type]


class TestWebCrawlSourceConnector(unittest.IsolatedAsyncioTestCase):
    async def test_yields_documents(self) -> None:
        connector = _http_connector({"http://x/a": b"AAA", "http://x/b": b"BBB"})
        crawl = WebCrawlSourceConnector(connector=connector, urls=["http://x/a", "http://x/b"])
        docs = [doc async for doc in crawl.fetch()]
        assert [d.source_id for d in docs] == ["http://x/a", "http://x/b"]
        assert docs[0].metadata["source"] == "web_crawl"

    async def test_rate_limit_failure_isolated(self) -> None:
        connector = _http_connector(
            {"http://x/ok": b"data", "http://x/429": RuntimeError("429 rate limited")}
        )
        crawl = WebCrawlSourceConnector(connector=connector, urls=["http://x/ok", "http://x/429"])
        docs = [doc async for doc in crawl.fetch()]
        assert [d.source_id for d in docs] == ["http://x/ok"]
        assert crawl.errors[0][0] == "http://x/429"
        assert "429" in crawl.errors[0][1]

    async def test_shared_deduplicator_across_connectors(self) -> None:
        dedup = ContentHashDeduplicator()
        store = _StubBlobStore({"a": b"shared"})
        obj = ObjectStoreSourceConnector(blob_store=store, deduplicator=dedup)
        first = [doc async for doc in obj.fetch()]
        assert len(first) == 1
        crawl = WebCrawlSourceConnector(
            connector=_http_connector({"http://x": b"shared"}),
            urls=["http://x"],
            deduplicator=dedup,
        )
        second = [doc async for doc in crawl.fetch()]
        assert second == []  # identical content already seen by the shared dedup

    def test_wrong_connector_type_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be an HttpConnector"):
            WebCrawlSourceConnector(connector=object(), urls=[])  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
