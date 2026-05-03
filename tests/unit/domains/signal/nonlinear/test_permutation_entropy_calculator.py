"""Unit tests for :class:`PermutationEntropyCalculator`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.nonlinear.permutation_entropy_calculator import PermutationEntropyCalculator
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_order_below_two(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="order"):
                PermutationEntropyCalculator(
                    signal=sig,
                    order=1,
                    delay=1,
                    _config=KnotConfig(id="pe"),
                )

    def test_rejects_order_above_eight(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="order"):
                PermutationEntropyCalculator(
                    signal=sig,
                    order=9,
                    delay=1,
                    _config=KnotConfig(id="pe"),
                )

    def test_rejects_non_positive_delay(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="delay"):
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


@pytest.mark.asyncio
class TestProcess:
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
