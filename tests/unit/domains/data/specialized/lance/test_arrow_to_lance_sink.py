"""Tests for :class:`ArrowToLanceSink`.

Construction-time guards do not require the lance dependency. The
end-to-end write test skips when the actual ``lance.write_dataset`` API
is missing (the PyPI ``lance`` placeholder package does not provide it).
"""

from __future__ import annotations

from typing import Any

import pyarrow as pa
import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.specialized.lance.arrow_to_lance_sink import ArrowToLanceSink
from pirn.tapestry import Tapestry


@knot
async def _emit_table() -> Any:
    """Emits a PyArrow Table; typed Any so pirn IO validation does not
    try to pydantic-schema raw ``pyarrow.Table`` (which is not
    pydantic-compatible)."""
    return pa.table({"id": [1, 2, 3], "name": ["a", "b", "c"]})


class TestArrowToLanceSinkConstruction:
    def test_rejects_empty_path(self) -> None:
        with Tapestry():
            tbl = _emit_table(_config=KnotConfig(id="t"))
            with pytest.raises(ValueError, match="non-empty"):
                ArrowToLanceSink(table=tbl, path="", _config=KnotConfig(id="sink"))

    def test_rejects_unknown_mode(self) -> None:
        with Tapestry():
            tbl = _emit_table(_config=KnotConfig(id="t"))
            with pytest.raises(ValueError, match="mode must be one of"):
                ArrowToLanceSink(
                    table=tbl, path="/tmp/x.lance", mode="bogus",
                    _config=KnotConfig(id="sink"),
                )

    def test_accepts_known_modes(self) -> None:
        with Tapestry():
            tbl = _emit_table(_config=KnotConfig(id="t"))
            sink = ArrowToLanceSink(
                table=tbl, path="/tmp/x.lance", mode="overwrite",
                _config=KnotConfig(id="sink"),
            )
        assert sink.mode == "overwrite"
        assert sink.path == "/tmp/x.lance"


@pytest.mark.asyncio
class TestArrowToLanceSinkProcess:
    async def test_writes_dataset_to_disk(self, tmp_path) -> None:
        lance = pytest.importorskip("lance")
        if not hasattr(lance, "write_dataset") or not hasattr(lance, "dataset"):
            pytest.skip(
                "Installed 'lance' package is the unrelated codegen "
                "package, not pylance"
            )

        path = str(tmp_path / "out.lance")
        with Tapestry() as t:
            tbl = _emit_table(_config=KnotConfig(id="t"))
            ArrowToLanceSink(table=tbl, path=path, _config=KnotConfig(id="sink"))
        result = await t.run(RunRequest())

        assert result.outputs["sink"] == path
        # Read it back to confirm the dataset is on disk.
        ds = lance.dataset(path)
        assert ds.to_table().num_rows == 3
