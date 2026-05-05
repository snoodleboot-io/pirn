"""Unit tests for :class:`PCADecomposer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.separation.pca_decomposer import PCADecomposer
from pirn.domains.signal.types.source_frame import SourceFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_component_count(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "component_count"):
                PCADecomposer(
                    signal=sig,
                    component_count=0,
                    _config=KnotConfig(id="pca"),
                )

    def test_rejects_non_bool_whiten(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(TypeError, "whiten"):
                PCADecomposer(
                    signal=sig,
                    component_count=2,
                    whiten="yes",  # type: ignore[arg-type]
                    _config=KnotConfig(id="pca"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_source_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            PCADecomposer(
                signal=sig,
                component_count=2,
                _config=KnotConfig(id="pca"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["pca"]
        assert isinstance(out, SourceFrame)
        assert out.source_count == 2
