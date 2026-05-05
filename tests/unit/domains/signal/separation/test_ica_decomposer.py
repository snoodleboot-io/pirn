"""Unit tests for :class:`ICADecomposer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.separation.ica_decomposer import ICADecomposer
from pirn.domains.signal.types.source_frame import SourceFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_source_count(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "source_count"):
                ICADecomposer(
                    signal=sig,
                    source_count=0,
                    _config=KnotConfig(id="ica"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_source_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ICADecomposer(
                signal=sig,
                source_count=3,
                _config=KnotConfig(id="ica"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["ica"]
        assert isinstance(out, SourceFrame)
        assert out.source_count == 3
        assert out.mixing_matrix_shape == (1, 3)
