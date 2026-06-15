"""Tests for :class:`ArrowToLanceSink`."""

from __future__ import annotations

import unittest

try:
    import pyarrow  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pyarrow not installed") from _e

try:
    from lance.dataset import write_dataset as _lance_write_dataset  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("lance not installed") from _e

import tempfile
from pathlib import Path
from typing import Any

import pyarrow as pa
from lance.dataset import LanceDataset as _LanceDataset
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.specialized.lance.arrow_to_lance_sink import ArrowToLanceSink


@knot
async def _emit_table() -> Any:
    """Typed Any so pirn IO validation does not try to pydantic-schema
    raw ``pyarrow.Table``."""
    return pa.table({"id": [1, 2, 3], "name": ["a", "b", "c"]})


class TestArrowToLanceSink(unittest.IsolatedAsyncioTestCase):
    async def test_writes_dataset_to_disk(self) -> None:
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        path = str(Path(tmp_dir.name) / "out.lance")
        with Tapestry() as t:
            tbl = _emit_table(_config=KnotConfig(id="t"))
            ArrowToLanceSink(table=tbl, path=path, _config=KnotConfig(id="sink"))
        result = await t.run(RunRequest())
        assert result.outputs["sink"] == path
        ds = _LanceDataset(path)
        assert ds.to_table().num_rows == 3


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_path_from_upstream_knot(self) -> None:
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        expected_path = str(Path(tmp_dir.name) / "wired.lance")

        @knot
        async def emit_path() -> str:
            return expected_path

        with Tapestry() as t:
            tbl = _emit_table(_config=KnotConfig(id="t"))
            path_knot = emit_path(_config=KnotConfig(id="path"))
            ArrowToLanceSink(
                table=tbl, path=path_knot, _config=KnotConfig(id="sink")
            )
        result = await t.run(RunRequest())
        assert result.outputs["sink"] == expected_path


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_sink(self, **kwargs: Any) -> ArrowToLanceSink:
        defaults: dict[str, Any] = {"path": "/tmp/x.lance", "mode": "create"}
        defaults.update(kwargs)
        with Tapestry():
            tbl = _emit_table(_config=KnotConfig(id="t"))
            return ArrowToLanceSink(table=tbl, _config=KnotConfig(id="sink"), **defaults)

    async def test_rejects_empty_path(self) -> None:
        k = self._make_sink(path="placeholder")
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(table=pa.table({}), path="", mode="create")

    async def test_rejects_unknown_mode(self) -> None:
        k = self._make_sink()
        with self.assertRaisesRegex(ValueError, "mode must be one of"):
            await k.process(table=pa.table({}), path="/tmp/x.lance", mode="bogus")

    async def test_accepts_known_modes(self) -> None:
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        path = str(Path(tmp_dir.name) / "x.lance")
        k = self._make_sink(path=path, mode="overwrite")
        result = await k.process(
            table=pa.table({"id": [1]}), path=path, mode="overwrite"
        )
        assert result == path
