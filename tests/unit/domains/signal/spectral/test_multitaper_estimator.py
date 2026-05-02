"""Unit tests for :class:`MultitaperEstimator`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.spectral.multitaper_estimator import MultitaperEstimator
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_non_positive_time_bandwidth(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="positive"):
                MultitaperEstimator(
                    signal=sig,
                    time_bandwidth=0,
                    taper_count=4,
                    _config=KnotConfig(id="m"),
                )

    def test_rejects_non_positive_taper_count(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="positive integer"):
                MultitaperEstimator(
                    signal=sig,
                    time_bandwidth=4.0,
                    taper_count=0,
                    _config=KnotConfig(id="m"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_spectrum_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            MultitaperEstimator(
                signal=sig,
                time_bandwidth=4.0,
                taper_count=7,
                _config=KnotConfig(id="m"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["m"]
        assert isinstance(out, SpectrumFrame)
        assert out.frequency_bins == 1024 // 2 + 1
