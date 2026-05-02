"""Unit tests for :class:`ChebyshevType2Filter`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.filters.chebyshev_type2_filter import ChebyshevType2Filter
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_non_positive_order(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="positive integer"):
                ChebyshevType2Filter(
                    signal=sig,
                    order=0,
                    stopband_attenuation_db=20.0,
                    cutoff_hz=10.0,
                    _config=KnotConfig(id="c"),
                )

    def test_rejects_non_positive_attenuation(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="stopband_attenuation_db"):
                ChebyshevType2Filter(
                    signal=sig,
                    order=4,
                    stopband_attenuation_db=0,
                    cutoff_hz=10.0,
                    _config=KnotConfig(id="c"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ChebyshevType2Filter(
                signal=sig,
                order=4,
                stopband_attenuation_db=40.0,
                cutoff_hz=50.0,
                _config=KnotConfig(id="c"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["c"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:cheby2"
