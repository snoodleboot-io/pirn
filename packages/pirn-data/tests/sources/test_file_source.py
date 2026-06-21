"""Tests for FileSource."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator
from typing import Any

from pirn.connectors.file_format import FileFormat
from pirn.connectors.object_store import ObjectStore
from pirn.core.knot_config import KnotConfig
from pirn_data.data_batch import DataBatch
from pirn_data.data_schema import DataSchema
from pirn_data.sources.file_source import FileSource


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


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_store(self) -> _FakeStore:
        return _FakeStore()

    def _make_format(self) -> _FakeFormat:
        return _FakeFormat([])

    def _make_fs(self, **overrides: Any) -> FileSource:
        return FileSource(
            store=self._make_store(),
            format=self._make_format(),
            key="data.parquet",
            _config=KnotConfig(id="fs"),
            **overrides,
        )

    async def test_rejects_non_object_store(self) -> None:
        fs = self._make_fs()
        with self.assertRaisesRegex(TypeError, "ObjectStore"):
            await fs.process(
                store=object(),  # type: ignore[arg-type]
                format=self._make_format(),
                key="data.parquet",
            )

    async def test_rejects_non_file_format(self) -> None:
        fs = self._make_fs()
        with self.assertRaisesRegex(TypeError, "FileFormat"):
            await fs.process(
                store=self._make_store(),
                format=object(),  # type: ignore[arg-type]
                key="data.parquet",
            )

    async def test_rejects_empty_key(self) -> None:
        fs = self._make_fs()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await fs.process(
                store=self._make_store(),
                format=self._make_format(),
                key="",
            )

    async def test_rejects_non_string_key(self) -> None:
        fs = self._make_fs()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await fs.process(
                store=self._make_store(),
                format=self._make_format(),
                key=None,  # type: ignore[arg-type]
            )

    async def test_rejects_invalid_schema(self) -> None:
        fs = self._make_fs()
        with self.assertRaisesRegex(TypeError, "DataSchema"):
            await fs.process(
                store=self._make_store(),
                format=self._make_format(),
                key="f.csv",
                schema=object(),  # type: ignore[arg-type]
            )

    async def test_default_source_uri_includes_key(self) -> None:
        fs = self._make_fs()
        batch = await fs.process(
            store=self._make_store(),
            format=self._make_format(),
            key="data.csv",
        )
        assert "data.csv" in batch.source_uri

    async def test_custom_source_uri_preserved(self) -> None:
        fs = self._make_fs()
        batch = await fs.process(
            store=self._make_store(),
            format=self._make_format(),
            key="data.csv",
            source_uri="s3://bucket/data.csv",
        )
        assert batch.source_uri == "s3://bucket/data.csv"


class TestFileSource(unittest.IsolatedAsyncioTestCase):
    def _make_fs(self, **kwargs: Any) -> FileSource:
        return FileSource(
            store=_FakeStore(),
            format=_FakeFormat([]),
            key="placeholder",
            _config=KnotConfig(id="fs"),
            **kwargs,
        )

    async def test_process_returns_data_batch(self) -> None:
        rows = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        fs = self._make_fs()
        batch = await fs.process(
            store=_FakeStore(b"fake-content"),
            format=_FakeFormat(rows),
            key="data.csv",
        )
        assert isinstance(batch, DataBatch)

    async def test_process_rows_match_format_output(self) -> None:
        fs = self._make_fs()
        batch = await fs.process(
            store=_FakeStore(b"data"),
            format=_FakeFormat([{"x": 1}, {"x": 2}]),
            key="data.csv",
        )
        assert len(batch.rows) == 2
        assert batch.rows[0]["x"] == 1

    async def test_process_empty_format_returns_empty_batch(self) -> None:
        fs = self._make_fs()
        batch = await fs.process(
            store=_FakeStore(b"data"),
            format=_FakeFormat([]),
            key="empty.csv",
        )
        assert batch.rows == ()

    async def test_process_schema_propagated_to_batch(self) -> None:
        schema = DataSchema(columns={"x": int})
        fs = self._make_fs()
        batch = await fs.process(
            store=_FakeStore(b"data"),
            format=_FakeFormat([{"x": 1}]),
            key="data.csv",
            schema=schema,
        )
        assert batch.schema == schema

    async def test_process_source_uri_in_batch(self) -> None:
        fs = self._make_fs()
        batch = await fs.process(
            store=_FakeStore(b"data"),
            format=_FakeFormat([]),
            key="my.csv",
        )
        assert "my.csv" in batch.source_uri
