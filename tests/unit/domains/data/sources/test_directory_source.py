"""Tests for DirectorySource."""

from __future__ import annotations

import unittest
from typing import Any, AsyncIterator

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.file_format import FileFormat
from pirn.domains.connectors.object_store import ObjectStore
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.data_schema import DataSchema
from pirn.domains.data.sources.directory_source import DirectorySource


class _FakeStore(ObjectStore):
    def __init__(self, files: dict[str, bytes] | None = None) -> None:
        self._files: dict[str, bytes] = files or {}

    async def get(self, key: str) -> AsyncIterator[bytes]:
        content = self._files.get(key, b"")

        async def _gen() -> AsyncIterator[bytes]:
            yield content

        return _gen()

    async def put(self, key: str, body: Any) -> None:
        pass

    async def list(self, prefix: str = "") -> AsyncIterator[str]:
        matching = [k for k in self._files if k.startswith(prefix)]

        async def _gen() -> AsyncIterator[str]:
            for k in matching:
                yield k

        return _gen()


class _FakeFormat(FileFormat):
    def __init__(self, row_map: dict[bytes, list[dict[str, Any]]] | None = None) -> None:
        self._row_map: dict[bytes, list[dict[str, Any]]] = row_map or {}

    @property
    def name(self) -> str:
        return "fake"

    async def read(self, body: Any) -> AsyncIterator[dict[str, Any]]:
        content = b"".join([c async for c in body]) if hasattr(body, "__aiter__") else b""
        rows = self._row_map.get(content, [])

        async def _gen() -> AsyncIterator[dict[str, Any]]:
            for r in rows:
                yield r

        return _gen()


def _make_simple_format(rows: list[dict[str, Any]]) -> "_FakeFormat":
    class _SimpleFormat(FileFormat):
        @property
        def name(self) -> str:
            return "simple"

        async def read(self, body: Any) -> AsyncIterator[dict[str, Any]]:
            async def _gen() -> AsyncIterator[dict[str, Any]]:
                for r in rows:
                    yield r

            return _gen()

    return _SimpleFormat()


class TestDirectorySourceConstruction(unittest.TestCase):
    def _make_store(self) -> _FakeStore:
        return _FakeStore()

    def _make_format(self) -> FileFormat:
        return _make_simple_format([])

    def test_rejects_non_object_store(self) -> None:
        with self.assertRaisesRegex(TypeError, "ObjectStore"):
            DirectorySource(
                store=object(),  # type: ignore
                format=self._make_format(),
                prefix="data/",
                _config=KnotConfig(id="ds"),
            )

    def test_rejects_non_file_format(self) -> None:
        with self.assertRaisesRegex(TypeError, "FileFormat"):
            DirectorySource(
                store=self._make_store(),
                format=object(),  # type: ignore
                prefix="data/",
                _config=KnotConfig(id="ds"),
            )

    def test_rejects_non_string_prefix(self) -> None:
        with self.assertRaisesRegex(TypeError, "string"):
            DirectorySource(
                store=self._make_store(),
                format=self._make_format(),
                prefix=None,  # type: ignore
                _config=KnotConfig(id="ds"),
            )

    def test_rejects_invalid_schema(self) -> None:
        with self.assertRaisesRegex(TypeError, "DataSchema"):
            DirectorySource(
                store=self._make_store(),
                format=self._make_format(),
                prefix="",
                schema=object(),  # type: ignore
                _config=KnotConfig(id="ds"),
            )

    def test_prefix_property(self) -> None:
        ds = DirectorySource(
            store=self._make_store(),
            format=self._make_format(),
            prefix="my/prefix/",
            _config=KnotConfig(id="ds"),
        )
        self.assertEqual(ds.prefix, "my/prefix/")

    def test_concatenate_default_false(self) -> None:
        ds = DirectorySource(
            store=self._make_store(),
            format=self._make_format(),
            prefix="",
            _config=KnotConfig(id="ds"),
        )
        self.assertFalse(ds.concatenate)

    def test_concatenate_true(self) -> None:
        ds = DirectorySource(
            store=self._make_store(),
            format=self._make_format(),
            prefix="",
            concatenate=True,
            _config=KnotConfig(id="ds"),
        )
        self.assertTrue(ds.concatenate)


class TestDirectorySourceProcess(unittest.IsolatedAsyncioTestCase):
    async def test_empty_prefix_yields_empty_tuple(self) -> None:
        store = _FakeStore({})
        fmt = _make_simple_format([])
        ds = DirectorySource(store=store, format=fmt, prefix="data/", _config=KnotConfig(id="ds"))
        result = await ds.process()
        self.assertEqual(result, ())

    async def test_per_file_mode_returns_tuple_of_batches(self) -> None:
        store = _FakeStore({"data/a.csv": b"", "data/b.csv": b""})
        fmt = _make_simple_format([{"x": 1}])
        ds = DirectorySource(store=store, format=fmt, prefix="data/", _config=KnotConfig(id="ds"))
        result = await ds.process()
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        for batch in result:
            self.assertIsInstance(batch, DataBatch)

    async def test_per_file_source_uris_per_key(self) -> None:
        store = _FakeStore({"dir/file1.csv": b""})
        fmt = _make_simple_format([])
        ds = DirectorySource(store=store, format=fmt, prefix="dir/", _config=KnotConfig(id="ds"))
        result = await ds.process()
        self.assertEqual(len(result), 1)
        self.assertIn("file1.csv", result[0].source_uri)

    async def test_concatenate_returns_single_batch(self) -> None:
        store = _FakeStore({"f1.csv": b"", "f2.csv": b""})
        fmt = _make_simple_format([{"x": 1}])
        ds = DirectorySource(
            store=store,
            format=fmt,
            prefix="",
            concatenate=True,
            _config=KnotConfig(id="ds"),
        )
        result = await ds.process()
        self.assertIsInstance(result, DataBatch)

    async def test_concatenate_combines_all_rows(self) -> None:
        store = _FakeStore({"f1.csv": b"", "f2.csv": b""})
        fmt = _make_simple_format([{"x": 1}, {"x": 2}])
        ds = DirectorySource(
            store=store,
            format=fmt,
            prefix="",
            concatenate=True,
            _config=KnotConfig(id="ds"),
        )
        result = await ds.process()
        # 2 rows per file × 2 files = 4 rows
        self.assertEqual(len(result.rows), 4)

    async def test_schema_propagated_to_batches(self) -> None:
        schema = DataSchema(columns={"x": int})
        store = _FakeStore({"f.csv": b""})
        fmt = _make_simple_format([{"x": 1}])
        ds = DirectorySource(
            store=store,
            format=fmt,
            prefix="",
            schema=schema,
            _config=KnotConfig(id="ds"),
        )
        result = await ds.process()
        for batch in result:
            self.assertEqual(batch.schema, schema)

    async def test_keys_sorted_in_output(self) -> None:
        files = {"dir/c.csv": b"", "dir/a.csv": b"", "dir/b.csv": b""}
        store = _FakeStore(files)
        fmt = _make_simple_format([])
        ds = DirectorySource(store=store, format=fmt, prefix="dir/", _config=KnotConfig(id="ds"))
        result = await ds.process()
        uris = [b.source_uri for b in result]
        self.assertEqual(uris, sorted(uris))
