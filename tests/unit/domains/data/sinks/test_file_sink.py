"""Tests for FileSink."""

from __future__ import annotations

import unittest
from typing import Any, AsyncIterator

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.file_format import FileFormat
from pirn.domains.connectors.object_store import ObjectStore
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


def _make_batch_knot(tapestry: Tapestry, knot_id: str = "batch") -> _BatchSource:
    with tapestry:
        return _BatchSource(_config=KnotConfig(id=knot_id))


class TestFileSinkConstruction(unittest.TestCase):
    def _store(self) -> _FakeStore:
        return _FakeStore()

    def _fmt(self) -> _FakeFormat:
        return _FakeFormat()

    def test_rejects_non_object_store(self) -> None:
        with Tapestry() as t:
            batch = _BatchSource(_config=KnotConfig(id="batch"))
            with self.assertRaisesRegex(TypeError, "ObjectStore"):
                FileSink(
                    batch=batch,
                    store=object(),  # type: ignore
                    format=self._fmt(),
                    key="out.csv",
                    _config=KnotConfig(id="sink"),
                )

    def test_rejects_non_file_format(self) -> None:
        with Tapestry():
            batch = _BatchSource(_config=KnotConfig(id="batch"))
            with self.assertRaisesRegex(TypeError, "FileFormat"):
                FileSink(
                    batch=batch,
                    store=self._store(),
                    format=object(),  # type: ignore
                    key="out.csv",
                    _config=KnotConfig(id="sink"),
                )

    def test_rejects_empty_key(self) -> None:
        with Tapestry():
            batch = _BatchSource(_config=KnotConfig(id="batch"))
            with self.assertRaisesRegex(ValueError, "non-empty"):
                FileSink(
                    batch=batch,
                    store=self._store(),
                    format=self._fmt(),
                    key="",
                    _config=KnotConfig(id="sink"),
                )

    def test_key_property(self) -> None:
        with Tapestry():
            batch = _BatchSource(_config=KnotConfig(id="batch"))
            sink = FileSink(
                batch=batch,
                store=self._store(),
                format=self._fmt(),
                key="output/file.parquet",
                _config=KnotConfig(id="sink"),
            )
        self.assertEqual(sink.key, "output/file.parquet")

    def test_format_name_property(self) -> None:
        with Tapestry():
            batch = _BatchSource(_config=KnotConfig(id="batch"))
            sink = FileSink(
                batch=batch,
                store=self._store(),
                format=self._fmt(),
                key="out.csv",
                _config=KnotConfig(id="sink"),
            )
        self.assertEqual(sink.format_name, "fake")


class TestFileSinkProcess(unittest.IsolatedAsyncioTestCase):
    def _store(self) -> _FakeStore:
        return _FakeStore()

    def _fmt(self) -> _FakeFormat:
        return _FakeFormat()

    async def test_process_returns_key(self) -> None:
        store = self._store()
        with Tapestry():
            batch = _BatchSource(_config=KnotConfig(id="batch"))
            sink = FileSink(
                batch=batch,
                store=store,
                format=self._fmt(),
                key="out.csv",
                _config=KnotConfig(id="sink"),
            )
        result = await sink.process(batch=_make_batch([{"x": 1}]))
        self.assertEqual(result, "out.csv")

    async def test_process_writes_to_store(self) -> None:
        store = self._store()
        with Tapestry():
            batch = _BatchSource(_config=KnotConfig(id="batch"))
            sink = FileSink(
                batch=batch,
                store=store,
                format=self._fmt(),
                key="output.csv",
                _config=KnotConfig(id="sink"),
            )
        await sink.process(batch=_make_batch([{"id": 1}, {"id": 2}]))
        self.assertIn("output.csv", store._stored)

    async def test_process_empty_batch(self) -> None:
        store = self._store()
        with Tapestry():
            batch = _BatchSource(_config=KnotConfig(id="batch"))
            sink = FileSink(
                batch=batch,
                store=store,
                format=self._fmt(),
                key="empty.csv",
                _config=KnotConfig(id="sink"),
            )
        result = await sink.process(batch=_make_batch([]))
        self.assertEqual(result, "empty.csv")
        self.assertIn("empty.csv", store._stored)

    async def test_process_encodes_rows_via_format(self) -> None:
        store = self._store()
        with Tapestry():
            batch = _BatchSource(_config=KnotConfig(id="batch"))
            sink = FileSink(
                batch=batch,
                store=store,
                format=self._fmt(),
                key="data.csv",
                _config=KnotConfig(id="sink"),
            )
        await sink.process(batch=_make_batch([{"name": "Alice"}]))
        raw = store._stored["data.csv"]
        self.assertIn(b"Alice", raw)
