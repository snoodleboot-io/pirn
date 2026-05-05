"""Tests for FileSource."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator
from typing import Any

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


class TestValidation(unittest.TestCase):
    def _make_store(self) -> _FakeStore:
        return _FakeStore()

    def _make_format(self) -> _FakeFormat:
        return _FakeFormat([])

    def test_rejects_non_object_store(self) -> None:
        with self.assertRaisesRegex(TypeError, "ObjectStore"):
            FileSource(
                store=object(),  # type: ignore[arg-type]
                format=self._make_format(),
                key="data.parquet",
                _config=KnotConfig(id="fs"),
            )

    def test_rejects_non_file_format(self) -> None:
        with self.assertRaisesRegex(TypeError, "FileFormat"):
            FileSource(
                store=self._make_store(),
                format=object(),  # type: ignore[arg-type]
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
                key=None,  # type: ignore[arg-type]
                _config=KnotConfig(id="fs"),
            )

    def test_rejects_invalid_schema(self) -> None:
        with self.assertRaisesRegex(TypeError, "DataSchema"):
            FileSource(
                store=self._make_store(),
                format=self._make_format(),
                key="f.csv",
                schema=object(),  # type: ignore[arg-type]
                _config=KnotConfig(id="fs"),
            )

    def test_key_property(self) -> None:
        fs = FileSource(
            store=self._make_store(),
            format=self._make_format(),
            key="path/to/file.csv",
            _config=KnotConfig(id="fs"),
        )
        assert fs.key == "path/to/file.csv"

    def test_format_name_property(self) -> None:
        fs = FileSource(
            store=self._make_store(),
            format=_FakeFormat([]),
            key="f.csv",
            _config=KnotConfig(id="fs"),
        )
        assert fs.format_name == "fake"

    def test_default_source_uri_includes_key(self) -> None:
        fs = FileSource(
            store=_FakeStore(),
            format=_FakeFormat([]),
            key="data.csv",
            _config=KnotConfig(id="fs"),
        )
        assert "data.csv" in fs._source_uri

    def test_custom_source_uri_preserved(self) -> None:
        fs = FileSource(
            store=_FakeStore(),
            format=_FakeFormat([]),
            key="data.csv",
            source_uri="s3://bucket/data.csv",
            _config=KnotConfig(id="fs"),
        )
        assert fs._source_uri == "s3://bucket/data.csv"


class TestFileSource(unittest.IsolatedAsyncioTestCase):
    async def test_process_returns_data_batch(self) -> None:
        rows = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        fs = FileSource(
            store=_FakeStore(b"fake-content"),
            format=_FakeFormat(rows),
            key="data.csv",
            _config=KnotConfig(id="fs"),
        )
        batch = await fs.process()
        assert isinstance(batch, DataBatch)

    async def test_process_rows_match_format_output(self) -> None:
        fs = FileSource(
            store=_FakeStore(b"data"),
            format=_FakeFormat([{"x": 1}, {"x": 2}]),
            key="data.csv",
            _config=KnotConfig(id="fs"),
        )
        batch = await fs.process()
        assert len(batch.rows) == 2
        assert batch.rows[0]["x"] == 1

    async def test_process_empty_format_returns_empty_batch(self) -> None:
        fs = FileSource(
            store=_FakeStore(b"data"),
            format=_FakeFormat([]),
            key="empty.csv",
            _config=KnotConfig(id="fs"),
        )
        batch = await fs.process()
        assert batch.rows == ()

    async def test_process_schema_propagated_to_batch(self) -> None:
        schema = DataSchema(columns={"x": int})
        fs = FileSource(
            store=_FakeStore(b"data"),
            format=_FakeFormat([{"x": 1}]),
            key="data.csv",
            schema=schema,
            _config=KnotConfig(id="fs"),
        )
        batch = await fs.process()
        assert batch.schema == schema

    async def test_process_source_uri_in_batch(self) -> None:
        fs = FileSource(
            store=_FakeStore(b"data"),
            format=_FakeFormat([]),
            key="my.csv",
            _config=KnotConfig(id="fs"),
        )
        batch = await fs.process()
        assert "my.csv" in batch.source_uri
