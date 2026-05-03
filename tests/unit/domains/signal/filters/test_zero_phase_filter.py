"""Unit tests for :class:`ZeroPhaseFilter`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.filters.zero_phase_filter import ZeroPhaseFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_invalid_filter_type(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="filter_type"):
                ZeroPhaseFilter(
                    signal=sig,
                    filter_type="allpass",
                    cutoff_hz=100.0,
                    order=4,
                    _config=KnotConfig(id="f"),
                )

    def test_rejects_non_positive_order(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="positive integer"):
                ZeroPhaseFilter(
                    signal=sig,
                    filter_type="lowpass",
                    cutoff_hz=100.0,
                    order=0,
                    _config=KnotConfig(id="f"),
                )

    def test_rejects_scalar_cutoff_for_bandstop(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="bandpass/bandstop"):
                ZeroPhaseFilter(
                    signal=sig,
                    filter_type="bandstop",
                    cutoff_hz=100.0,
                    order=4,
                    _config=KnotConfig(id="f"),
                )

    def test_rejects_invalid_band_bounds(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="0 < low < high"):
                ZeroPhaseFilter(
                    signal=sig,
                    filter_type="bandpass",
                    cutoff_hz=(200.0, 100.0),
                    order=4,
                    _config=KnotConfig(id="f"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_signal_frame_with_type_marker(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ZeroPhaseFilter(
                signal=sig,
                filter_type="lowpass",
                cutoff_hz=100.0,
                order=4,
                _config=KnotConfig(id="f"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["f"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:zerophase-lowpass"
        assert out.sample_rate_hz == 1000.0
