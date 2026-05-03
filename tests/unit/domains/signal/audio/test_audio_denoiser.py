"""Unit tests for :class:`AudioDenoiser`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.audio.audio_denoiser import AudioDenoiser
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_non_positive_noise_estimate_frames(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="noise_estimate_frames"):
                AudioDenoiser(
                    signal=sig,
                    noise_estimate_frames=0,
                    over_subtraction_factor=1.5,
                    _config=KnotConfig(id="dn"),
                )

    def test_rejects_over_subtraction_factor_below_one(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="over_subtraction_factor"):
                AudioDenoiser(
                    signal=sig,
                    noise_estimate_frames=5,
                    over_subtraction_factor=0.5,
                    _config=KnotConfig(id="dn"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            dn = AudioDenoiser(
                signal=sig,
                noise_estimate_frames=10,
                over_subtraction_factor=1.0,
                _config=KnotConfig(id="dn"),
            )
        assert dn.noise_estimate_frames == 10
        assert dn.over_subtraction_factor == 1.0


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            AudioDenoiser(
                signal=sig,
                noise_estimate_frames=10,
                over_subtraction_factor=2.0,
                _config=KnotConfig(id="dn"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["dn"]
        assert isinstance(out, SignalFrame)
        assert out.sample_rate_hz == 1000.0
