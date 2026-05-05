"""Unit tests for :class:`DictionaryLearner`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.separation.dictionary_learner import DictionaryLearner
from pirn.domains.signal.types.source_frame import SourceFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_atom_count(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "atom_count"):
                DictionaryLearner(
                    signal=sig,
                    atom_count=0,
                    sparsity_target=2,
                    _config=KnotConfig(id="d"),
                )

    def test_rejects_non_positive_sparsity_target(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "sparsity_target"):
                DictionaryLearner(
                    signal=sig,
                    atom_count=4,
                    sparsity_target=0,
                    _config=KnotConfig(id="d"),
                )

    def test_rejects_sparsity_target_above_atom_count(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "not exceed"):
                DictionaryLearner(
                    signal=sig,
                    atom_count=4,
                    sparsity_target=8,
                    _config=KnotConfig(id="d"),
                )

    def test_rejects_non_positive_max_iterations(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "max_iterations"):
                DictionaryLearner(
                    signal=sig,
                    atom_count=4,
                    sparsity_target=2,
                    max_iterations=0,
                    _config=KnotConfig(id="d"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_source_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            DictionaryLearner(
                signal=sig,
                atom_count=8,
                sparsity_target=3,
                _config=KnotConfig(id="d"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["d"]
        assert isinstance(out, SourceFrame)
        assert out.source_count == 8
        assert out.mixing_matrix_shape == (1, 8)
