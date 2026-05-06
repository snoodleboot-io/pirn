"""Tests for :class:`LanceSource`.

End-to-end tests skip unless the actual ``lance.dataset`` /
``lance.write_dataset`` API is available — the PyPI ``lance`` placeholder
package does not provide it.
"""

from __future__ import annotations
import unittest
import tempfile
from pathlib import Path

import pytest

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
        _td_test_reads_lance_dataset_from_disk = tempfile.TemporaryDirectory()
        self.addCleanup(_td_test_reads_lance_dataset_from_disk.cleanup)
        tmp_path = Path(_td_test_reads_lance_dataset_from_disk.name)
        try:
            import lance
        except ImportError as _e:
            self.skipTest("lance not installed")
        if not hasattr(lance, "write_dataset") or not hasattr(lance, "dataset"):
            pytest.skip(
                "Installed 'lance' package is the unrelated codegen "
                "package, not pylance"
            )
        try:
            import pyarrow
        except ImportError as _e:
            self.skipTest("pyarrow not installed")

        table = pyarrow.table({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        path = str(tmp_path / "ds.lance")
        lance.write_dataset(table, path)

        with Tapestry() as t:
            LanceSource(path=path, _config=KnotConfig(id="src"))
        result = await t.run(RunRequest())

        emitted = result.outputs["src"]
        assert isinstance(emitted, LanceDataset)
        assert emitted.source_uri == path
        # Round-trip through ``to_table`` to confirm the dataset is real.
        assert emitted.dataset.to_table().num_rows == 3
