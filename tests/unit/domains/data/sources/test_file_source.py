"""Tests for FileSource."""

from __future__ import annotations

import unittest
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.file_format import FileFormat
from pirn.domains.connectors.object_store import ObjectStore
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.data_schema import DataSchema
from pirn.domains.data.sources.file_source import FileSource


class _FakeStore(ObjectStore):
    def __init__(self, content: bytes = b"") -> None:
        self._content = content

    async def get(self, key: str) -> AsyncIterator[bytes]:
        async def _gen() -> AsyncIterator[bytes]:
            yield self._content

        return _gen()

    async def put(self, key: str, body: Any) -> None:
        pass

    async def list(self, prefix: str = "") -> AsyncIterator[str]:
        async def _gen() -> AsyncIterator[str]:
            return
            yield  # make it an async generator

        return _gen()


class _FakeFormat(FileFormat):
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    @property
    def name(self) -> str:
        return "fake"

    async def read(self, body: Any) -> AsyncIterator[dict[str, Any]]:
        async def _gen() -> AsyncIterator[dict[str, Any]]:
            for row in self._rows:
                yield row

        return _gen()


class TestFileSourceConstruction(unittest.TestCase):
    def _make_store(self) -> _FakeStore:
        return _FakeStore()

    def _make_format(self) -> _FakeFormat:
        return _FakeFormat([])

    def test_rejects_non_object_store(self) -> None:
        with self.assertRaisesRegex(TypeError, "ObjectStore"):
            FileSource(
                store=object(),  # type: ignore
                format=self._make_format(),
                key="data.parquet",
                _config=KnotConfig(id="fs"),
            )

    def test_rejects_non_file_format(self) -> None:
        with self.assertRaisesRegex(TypeError, "FileFormat"):
            FileSource(
                store=self._make_store(),
                format=object(),  # type: ignore
                key="data.parquet",
                _config=KnotConfig(id="fs"),
            )

    def test_rejects_empty_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            FileSource(
                store=self._make_store(),
                format=self._make_format(),
                key="",
                _config=KnotConfig(id="fs"),
            )

    def test_rejects_non_string_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            FileSource(
                store=self._make_store(),
                format=self._make_format(),
                key=None,  # type: ignore
                _config=KnotConfig(id="fs"),
            )

    def test_rejects_invalid_schema(self) -> None:
        with self.assertRaisesRegex(TypeError, "DataSchema"):
            FileSource(
                store=self._make_store(),
                format=self._make_format(),
                key="f.csv",
                schema=object(),  # type: ignore
                _config=KnotConfig(id="fs"),
            )

    def test_key_property(self) -> None:
        store = self._make_store()
        fmt = self._make_format()
        fs = FileSource(store=store, format=fmt, key="path/to/file.csv", _config=KnotConfig(id="fs"))
        self.assertEqual(fs.key, "path/to/file.csv")

    def test_format_name_property(self) -> None:
        store = self._make_store()
        fmt = _FakeFormat([])
        fs = FileSource(store=store, format=fmt, key="f.csv", _config=KnotConfig(id="fs"))
        self.assertEqual(fs.format_name, "fake")

    def test_default_source_uri_built_from_store_and_key(self) -> None:
        store = _FakeStore()
        fmt = _FakeFormat([])
        fs = FileSource(store=store, format=fmt, key="data.csv", _config=KnotConfig(id="fs"))
        self.assertIn("data.csv", fs._source_uri)

    def test_custom_source_uri_preserved(self) -> None:
        store = _FakeStore()
        fmt = _FakeFormat([])
        fs = FileSource(
            store=store,
            format=fmt,
            key="data.csv",
            source_uri="s3://bucket/data.csv",
            _config=KnotConfig(id="fs"),
        )
        self.assertEqual(fs._source_uri, "s3://bucket/data.csv")


class TestFileSourceProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_returns_data_batch(self) -> None:
        rows = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        store = _FakeStore(b"fake-content")
        fmt = _FakeFormat(rows)
        fs = FileSource(store=store, format=fmt, key="data.csv", _config=KnotConfig(id="fs"))
        batch = await fs.process()
        self.assertIsInstance(batch, DataBatch)

    async def test_process_rows_match_format_output(self) -> None:
        rows = [{"x": 1}, {"x": 2}]
        store = _FakeStore(b"data")
        fmt = _FakeFormat(rows)
        fs = FileSource(store=store, format=fmt, key="data.csv", _config=KnotConfig(id="fs"))
        batch = await fs.process()
        self.assertEqual(len(batch.rows), 2)
        self.assertEqual(batch.rows[0]["x"], 1)

    async def test_process_empty_format_returns_empty_batch(self) -> None:
        store = _FakeStore(b"data")
        fmt = _FakeFormat([])
        fs = FileSource(store=store, format=fmt, key="empty.csv", _config=KnotConfig(id="fs"))
        batch = await fs.process()
        self.assertEqual(batch.rows, ())

    async def test_process_schema_propagated_to_batch(self) -> None:
        schema = DataSchema(columns={"x": int})
        store = _FakeStore(b"data")
        fmt = _FakeFormat([{"x": 1}])
        fs = FileSource(
            store=store,
            format=fmt,
            key="data.csv",
            schema=schema,
            _config=KnotConfig(id="fs"),
        )
        batch = await fs.process()
        self.assertEqual(batch.schema, schema)

    async def test_process_source_uri_in_batch(self) -> None:
        store = _FakeStore(b"data")
        fmt = _FakeFormat([])
        fs = FileSource(store=store, format=fmt, key="my.csv", _config=KnotConfig(id="fs"))
        batch = await fs.process()
        self.assertIn("my.csv", batch.source_uri)
