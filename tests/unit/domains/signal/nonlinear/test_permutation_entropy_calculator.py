"""Unit tests for :class:`PermutationEntropyCalculator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.nonlinear.permutation_entropy_calculator import PermutationEntropyCalculator
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_order_below_two(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "order"):
                PermutationEntropyCalculator(
                    signal=sig,
                    order=1,
                    delay=1,
                    _config=KnotConfig(id="pe"),
                )

    def test_rejects_order_above_eight(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "order"):
                PermutationEntropyCalculator(
                    signal=sig,
                    order=9,
                    delay=1,
                    _config=KnotConfig(id="pe"),
                )

    def test_rejects_non_positive_delay(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "delay"):
                PermutationEntropyCalculator(
                    signal=sig,
                    order=3,
                    delay=0,
                    _config=KnotConfig(id="pe"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            pe = PermutationEntropyCalculator(
                signal=sig,
                order=4,
                delay=2,
                _config=KnotConfig(id="pe"),
            )
        assert pe.order == 4
        assert pe.delay == 2


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_entropy_dict(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            PermutationEntropyCalculator(
                signal=sig,
                order=4,
                delay=1,
                _config=KnotConfig(id="pe"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["pe"]
        assert isinstance(out, dict)
        assert "permutation_entropy" in out
        assert "normalized_entropy" in out
