"""Tests for :class:`LanceSource`."""

from __future__ import annotations

import unittest

try:
    import pyarrow  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pyarrow not installed") from _e

try:
    from lance.dataset import LanceDataset as _LanceDataset  # noqa: F401
    from lance.dataset import write_dataset as _lance_write_dataset  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("lance not installed") from _e

import tempfile
from pathlib import Path

import pyarrow as pa
from lance.dataset import LanceDataset as _LanceDataset
from lance.dataset import write_dataset

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.data.specialized.lance.lance_dataset import LanceDataset
from pirn.domains.data.specialized.lance.lance_source import LanceSource
from pirn.tapestry import Tapestry


class TestLanceSourceConstruction(unittest.TestCase):
    def test_accepts_non_empty_path(self) -> None:
        src = LanceSource(path="/tmp/x.lance", _config=KnotConfig(id="src"))
        self.assertIsInstance(src, LanceSource)


class TestLanceSourceProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_path(self) -> None:
        src = LanceSource(path="placeholder", _config=KnotConfig(id="src"))
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await src.process(path="")

    async def test_rejects_non_string_path(self) -> None:
        src = LanceSource(path="placeholder", _config=KnotConfig(id="src"))
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await src.process(path=123)  # type: ignore[arg-type]

    async def test_reads_lance_dataset_from_disk(self) -> None:
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        path = str(Path(tmp_dir.name) / "ds.lance")

        table = pa.table({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        write_dataset(table, path)

        with Tapestry() as t:
            LanceSource(path=path, _config=KnotConfig(id="src"))
        result = await t.run(RunRequest())

        emitted = result.outputs["src"]
        assert isinstance(emitted, LanceDataset)
        assert emitted.source_uri == path
        assert emitted.dataset.to_table().num_rows == 3
