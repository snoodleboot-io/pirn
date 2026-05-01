"""Tests for :class:`LanceSource`.

Construction-time guards run with no lance dependency required (the real
``lance`` package is only imported inside ``process()``). End-to-end
tests skip unless the actual ``lance.dataset`` /
``lance.write_dataset`` API is available — the PyPI ``lance`` placeholder
package does not provide it.
"""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.data.specialized.lance.lance_dataset import LanceDataset
from pirn.domains.data.specialized.lance.lance_source import LanceSource
from pirn.tapestry import Tapestry


class TestLanceSourceConstruction:
    def test_rejects_empty_path(self) -> None:
        with Tapestry():
            with pytest.raises(ValueError, match="non-empty"):
                LanceSource(path="", _config=KnotConfig(id="src"))

    def test_rejects_non_string_path(self) -> None:
        with Tapestry():
            with pytest.raises(ValueError, match="non-empty"):
                LanceSource(path=123, _config=KnotConfig(id="src"))  # type: ignore[arg-type]

    def test_path_is_exposed(self) -> None:
        with Tapestry():
            src = LanceSource(path="/tmp/x.lance", _config=KnotConfig(id="src"))
        assert src.path == "/tmp/x.lance"


@pytest.mark.asyncio
class TestLanceSourceProcess:
    async def test_reads_lance_dataset_from_disk(self, tmp_path) -> None:
        lance = pytest.importorskip("lance")
        if not hasattr(lance, "write_dataset") or not hasattr(lance, "dataset"):
            pytest.skip(
                "Installed 'lance' package is the unrelated codegen "
                "package, not pylance"
            )
        pa = pytest.importorskip("pyarrow")

        table = pa.table({"id": [1, 2, 3], "name": ["a", "b", "c"]})
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
