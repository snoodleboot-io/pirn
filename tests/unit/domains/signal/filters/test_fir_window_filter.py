"""Unit tests for :class:`FIRWindowFilter`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.filters.fir_window_filter import FIRWindowFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_even_num_taps(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="positive odd"):
                FIRWindowFilter(
                    signal=sig,
                    num_taps=64,
                    cutoff_hz=100.0,
                    window="hamming",
                    _config=KnotConfig(id="f"),
                )

    def test_rejects_non_positive_cutoff(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="positive scalar"):
                FIRWindowFilter(
                    signal=sig,
                    num_taps=63,
                    cutoff_hz=0.0,
                    window="hamming",
                    _config=KnotConfig(id="f"),
                )

    def test_rejects_invalid_window(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="window"):
                FIRWindowFilter(
                    signal=sig,
                    num_taps=63,
                    cutoff_hz=100.0,
                    window="kaiser",
                    _config=KnotConfig(id="f"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            FIRWindowFilter(
                signal=sig,
                num_taps=63,
                cutoff_hz=200.0,
                window="hann",
                _config=KnotConfig(id="f"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["f"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:fir-window"
        assert out.sample_rate_hz == 1000.0
