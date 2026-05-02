"""Unit tests for :class:`WelchEstimator`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.spectral.welch_estimator import WelchEstimator
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_requires_segment_length(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(TypeError):
                WelchEstimator(signal=sig, _config=KnotConfig(id="w"))  # type: ignore[call-arg]

    def test_rejects_non_positive_segment_length(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="positive integer"):
                WelchEstimator(
                    signal=sig, segment_length=0, _config=KnotConfig(id="w")
                )

    def test_rejects_negative_overlap(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="non-negative"):
                WelchEstimator(
                    signal=sig,
                    segment_length=64,
                    overlap=-1,
                    _config=KnotConfig(id="w"),
                )

    def test_rejects_overlap_ge_segment_length(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="smaller than"):
                WelchEstimator(
                    signal=sig,
                    segment_length=64,
                    overlap=64,
                    _config=KnotConfig(id="w"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_spectrum_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            WelchEstimator(
                signal=sig,
                segment_length=128,
                overlap=64,
                _config=KnotConfig(id="w"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["w"]
        assert isinstance(out, SpectrumFrame)
        assert out.frequency_bins == 65
        assert out.signal_id == "test"
