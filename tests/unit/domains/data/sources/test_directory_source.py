"""Tests for DirectorySource."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.connectors.file_format import FileFormat
from pirn.connectors.object_store import ObjectStore
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


def _make_simple_format(rows: list[dict[str, Any]]) -> FileFormat:
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


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_store(self) -> _FakeStore:
        return _FakeStore()

    def _make_format(self) -> FileFormat:
        return _make_simple_format([])

    def _make_ds(self, **overrides: Any) -> DirectorySource:
        return DirectorySource(
            store=self._make_store(),
            format=self._make_format(),
            prefix="data/",
            _config=KnotConfig(id="ds"),
            **overrides,
        )

    async def test_rejects_non_object_store(self) -> None:
        ds = self._make_ds()
        with self.assertRaisesRegex(TypeError, "ObjectStore"):
            await ds.process(
                store=object(),  # type: ignore[arg-type]
                format=self._make_format(),
                prefix="data/",
            )

    async def test_rejects_non_file_format(self) -> None:
        ds = self._make_ds()
        with self.assertRaisesRegex(TypeError, "FileFormat"):
            await ds.process(
                store=self._make_store(),
                format=object(),  # type: ignore[arg-type]
                prefix="data/",
            )

    async def test_rejects_non_string_prefix(self) -> None:
        ds = self._make_ds()
        with self.assertRaisesRegex(TypeError, "string"):
            await ds.process(
                store=self._make_store(),
                format=self._make_format(),
                prefix=None,  # type: ignore[arg-type]
            )

    async def test_rejects_invalid_schema(self) -> None:
        ds = self._make_ds()
        with self.assertRaisesRegex(TypeError, "DataSchema"):
            await ds.process(
                store=self._make_store(),
                format=self._make_format(),
                prefix="",
                schema=object(),  # type: ignore[arg-type]
            )


class TestDirectorySource(unittest.IsolatedAsyncioTestCase):
    def _make_ds(self, **overrides: Any) -> DirectorySource:
        return DirectorySource(
            store=_FakeStore(),
            format=_make_simple_format([]),
            prefix="",
            _config=KnotConfig(id="ds"),
            **overrides,
        )

    async def test_empty_prefix_yields_empty_tuple(self) -> None:
        ds = self._make_ds()
        result = await ds.process(
            store=_FakeStore({}),
            format=_make_simple_format([]),
            prefix="data/",
        )
        assert result == ()

    async def test_per_file_mode_returns_tuple_of_batches(self) -> None:
        ds = self._make_ds()
        result = await ds.process(
            store=_FakeStore({"data/a.csv": b"", "data/b.csv": b""}),
            format=_make_simple_format([{"x": 1}]),
            prefix="data/",
        )
        assert isinstance(result, tuple)
        assert len(result) == 2
        for batch in result:
            assert isinstance(batch, DataBatch)

    async def test_per_file_source_uris_per_key(self) -> None:
        ds = self._make_ds()
        result = await ds.process(
            store=_FakeStore({"dir/file1.csv": b""}),
            format=_make_simple_format([]),
            prefix="dir/",
        )
        assert len(result) == 1
        assert "file1.csv" in result[0].source_uri

    async def test_concatenate_returns_single_batch(self) -> None:
        ds = self._make_ds()
        result = await ds.process(
            store=_FakeStore({"f1.csv": b"", "f2.csv": b""}),
            format=_make_simple_format([{"x": 1}]),
            prefix="",
            concatenate=True,
        )
        assert isinstance(result, DataBatch)

    async def test_concatenate_combines_all_rows(self) -> None:
        ds = self._make_ds()
        result = await ds.process(
            store=_FakeStore({"f1.csv": b"", "f2.csv": b""}),
            format=_make_simple_format([{"x": 1}, {"x": 2}]),
            prefix="",
            concatenate=True,
        )
        assert len(result.rows) == 4

    async def test_schema_propagated_to_batches(self) -> None:
        schema = DataSchema(columns={"x": int})
        ds = self._make_ds()
        result = await ds.process(
            store=_FakeStore({"f.csv": b""}),
            format=_make_simple_format([{"x": 1}]),
            prefix="",
            schema=schema,
        )
        for batch in result:
            assert batch.schema == schema

    async def test_keys_sorted_in_output(self) -> None:
        ds = self._make_ds()
        result = await ds.process(
            store=_FakeStore({"dir/c.csv": b"", "dir/a.csv": b"", "dir/b.csv": b""}),
            format=_make_simple_format([]),
            prefix="dir/",
        )
        uris = [b.source_uri for b in result]
        assert uris == sorted(uris)
