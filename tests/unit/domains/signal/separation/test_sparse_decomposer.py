"""Unit tests for :class:`SparseDecomposer`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.separation.sparse_decomposer import SparseDecomposer
from pirn.domains.signal.types.source_frame import SourceFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_non_positive_atom_count(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="atom_count"):
                SparseDecomposer(
                    signal=sig,
                    atom_count=0,
                    sparsity_target=2,
                    _config=KnotConfig(id="sd"),
                )

    def test_rejects_non_positive_sparsity_target(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="sparsity_target"):
                SparseDecomposer(
                    signal=sig,
                    atom_count=4,
                    sparsity_target=0,
                    _config=KnotConfig(id="sd"),
                )

    def test_rejects_invalid_algorithm(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="algorithm"):
                SparseDecomposer(
                    signal=sig,
                    atom_count=4,
                    sparsity_target=2,
                    algorithm="bogus",
                    _config=KnotConfig(id="sd"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_source_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            SparseDecomposer(
                signal=sig,
                atom_count=8,
                sparsity_target=3,
                _config=KnotConfig(id="sd"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["sd"]
        assert isinstance(out, SourceFrame)
        assert out.source_count == 3
        assert out.mixing_matrix_shape == (1, 8)
