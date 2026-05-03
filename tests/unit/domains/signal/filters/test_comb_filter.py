"""Unit tests for :class:`CombFilter`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.filters.comb_filter import CombFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_non_positive_delay(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="delay_samples"):
                CombFilter(signal=sig, delay_samples=0, gain=0.5, _config=KnotConfig(id="f"))

    def test_rejects_gain_above_one(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="gain"):
                CombFilter(signal=sig, delay_samples=10, gain=1.1, _config=KnotConfig(id="f"))

    def test_rejects_negative_gain(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="gain"):
                CombFilter(signal=sig, delay_samples=10, gain=-0.1, _config=KnotConfig(id="f"))

    def test_accepts_boundary_gain_zero(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            CombFilter(signal=sig, delay_samples=5, gain=0.0, _config=KnotConfig(id="f"))

    def test_accepts_boundary_gain_one(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            CombFilter(signal=sig, delay_samples=5, gain=1.0, _config=KnotConfig(id="f"))


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            CombFilter(signal=sig, delay_samples=8, gain=0.5, _config=KnotConfig(id="f"))
        result = await t.run(RunRequest())
        out = result.outputs["f"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:comb"
        assert out.sample_rate_hz == 1000.0
