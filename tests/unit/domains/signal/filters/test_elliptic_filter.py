"""Unit tests for :class:`EllipticFilter`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.filters.elliptic_filter import EllipticFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_non_positive_order(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="positive integer"):
                EllipticFilter(
                    signal=sig,
                    order=0,
                    passband_ripple_db=1.0,
                    stopband_attenuation_db=40.0,
                    cutoff_hz=10.0,
                    _config=KnotConfig(id="e"),
                )

    def test_rejects_non_positive_ripple(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="passband_ripple_db"):
                EllipticFilter(
                    signal=sig,
                    order=4,
                    passband_ripple_db=0,
                    stopband_attenuation_db=40.0,
                    cutoff_hz=10.0,
                    _config=KnotConfig(id="e"),
                )

    def test_rejects_non_positive_attenuation(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="stopband_attenuation_db"):
                EllipticFilter(
                    signal=sig,
                    order=4,
                    passband_ripple_db=1.0,
                    stopband_attenuation_db=0,
                    cutoff_hz=10.0,
                    _config=KnotConfig(id="e"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            EllipticFilter(
                signal=sig,
                order=4,
                passband_ripple_db=1.0,
                stopband_attenuation_db=40.0,
                cutoff_hz=50.0,
                _config=KnotConfig(id="e"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["e"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:ellip"
