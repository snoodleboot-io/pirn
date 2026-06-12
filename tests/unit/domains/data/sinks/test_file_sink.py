"""Tests for FileSink."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.connectors.file_format import FileFormat
from pirn.connectors.object_store import ObjectStore
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.sinks.file_sink import FileSink
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


class _FakeStore(ObjectStore):
    def __init__(self) -> None:
        self._stored: dict[str, bytes] = {}

    async def get(self, key: str) -> AsyncIterator[bytes]:
        async def _gen() -> AsyncIterator[bytes]:
            yield self._stored.get(key, b"")

        return _gen()

    async def put(self, key: str, body: Any) -> None:
        if isinstance(body, bytes):
            self._stored[key] = body
        else:
            chunks: list[bytes] = []
            async for chunk in body:
                chunks.append(chunk)
            self._stored[key] = b"".join(chunks)

    async def list(self, prefix: str = "") -> AsyncIterator[str]:
        async def _gen() -> AsyncIterator[str]:
            for k in self._stored:
                if k.startswith(prefix):
                    yield k

        return _gen()


class _FakeFormat(FileFormat):
    @property
    def name(self) -> str:
        return "fake"

    async def write(self, records: Any) -> AsyncIterator[bytes]:
        rows: list[dict] = []
        async for row in records:
            rows.append(row)

        async def _gen() -> AsyncIterator[bytes]:
            yield str(rows).encode()

        return _gen()


class _BatchSource(Source):
    async def process(self, **_: Any) -> DataBatch:
        return DataBatch(rows=())


def _make_batch(rows: list[dict[str, Any]] | None = None) -> DataBatch:
    return DataBatch(rows=tuple(rows or []))


class TestFileSink(unittest.IsolatedAsyncioTestCase):
    def _store(self) -> _FakeStore:
        return _FakeStore()

    def _fmt(self) -> _FakeFormat:
        return _FakeFormat()

    def _make_sink(self, key: str = "out.csv") -> FileSink:
        with Tapestry():
            batch = _BatchSource(_config=KnotConfig(id="batch"))
            return FileSink(
                batch=batch,
                store=self._store(),
                format=self._fmt(),
                key=key,
                _config=KnotConfig(id="sink"),
            )

    async def test_process_returns_key(self) -> None:
        store = self._store()
        sink = self._make_sink("out.csv")
        result = await sink.process(
            batch=_make_batch([{"x": 1}]),
            store=store,
            format=self._fmt(),
            key="out.csv",
        )
        assert result == "out.csv"

    async def test_process_writes_to_store(self) -> None:
        store = self._store()
        sink = self._make_sink("output.csv")
        await sink.process(
            batch=_make_batch([{"id": 1}, {"id": 2}]),
            store=store,
            format=self._fmt(),
            key="output.csv",
        )
        assert "output.csv" in store._stored

    async def test_process_empty_batch(self) -> None:
        store = self._store()
        sink = self._make_sink("empty.csv")
        result = await sink.process(
            batch=_make_batch([]),
            store=store,
            format=self._fmt(),
            key="empty.csv",
        )
        assert result == "empty.csv"
        assert "empty.csv" in store._stored

    async def test_process_encodes_rows_via_format(self) -> None:
        store = self._store()
        sink = self._make_sink("data.csv")
        await sink.process(
            batch=_make_batch([{"name": "Alice"}]),
            store=store,
            format=self._fmt(),
            key="data.csv",
        )
        assert b"Alice" in store._stored["data.csv"]


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_key_from_upstream_knot(self) -> None:
        store = _FakeStore()
        fmt = _FakeFormat()

        @knot
        async def emit_batch() -> DataBatch:
            return DataBatch(rows=({"x": 1},))

        @knot
        async def emit_key() -> str:
            return "wired.csv"

        with Tapestry() as t:
            batch_knot = emit_batch(_config=KnotConfig(id="batch"))
            key_knot = emit_key(_config=KnotConfig(id="key"))
            FileSink(
                batch=batch_knot,
                store=store,
                format=fmt,
                key=key_knot,
                _config=KnotConfig(id="sink"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["sink"] == "wired.csv"
        assert "wired.csv" in store._stored


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_sink(self, **kwargs: Any) -> FileSink:
        store = _FakeStore()
        fmt = _FakeFormat()
        defaults: dict[str, Any] = {"store": store, "format": fmt, "key": "x.csv"}
        defaults.update(kwargs)
        with Tapestry():
            batch = _BatchSource(_config=KnotConfig(id="batch"))
            return FileSink(batch=batch, _config=KnotConfig(id="sink"), **defaults)

    async def test_rejects_non_object_store(self) -> None:
        k = self._make_sink()
        with self.assertRaisesRegex(TypeError, "ObjectStore"):
            await k.process(
                batch=_make_batch(), store=object(), format=_FakeFormat(), key="x.csv"
            )

    async def test_rejects_non_file_format(self) -> None:
        k = self._make_sink()
        with self.assertRaisesRegex(TypeError, "FileFormat"):
            await k.process(
                batch=_make_batch(), store=_FakeStore(), format=object(), key="x.csv"
            )

    async def test_rejects_empty_key(self) -> None:
        k = self._make_sink(key="placeholder.csv")
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(
                batch=_make_batch(), store=_FakeStore(), format=_FakeFormat(), key=""
            )
