"""Unit tests for :class:`SSADecomposer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.separation.ssa_decomposer import SSADecomposer
from pirn.domains.signal.types.source_frame import SourceFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_embedding_dim_le_one(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "embedding_dim"):
                SSADecomposer(
                    signal=sig,
                    embedding_dim=1,
                    component_count=1,
                    _config=KnotConfig(id="ssa"),
                )

    def test_rejects_non_positive_component_count(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "component_count"):
                SSADecomposer(
                    signal=sig,
                    embedding_dim=10,
                    component_count=0,
                    _config=KnotConfig(id="ssa"),
                )

    def test_rejects_component_count_above_embedding_dim(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "not exceed"):
                SSADecomposer(
                    signal=sig,
                    embedding_dim=4,
                    component_count=8,
                    _config=KnotConfig(id="ssa"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_source_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            SSADecomposer(
                signal=sig,
                embedding_dim=10,
                component_count=4,
                _config=KnotConfig(id="ssa"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["ssa"]
        assert isinstance(out, SourceFrame)
        assert out.source_count == 4
        assert out.mixing_matrix_shape == (10, 4)
