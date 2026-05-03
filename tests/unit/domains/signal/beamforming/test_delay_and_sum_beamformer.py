"""Unit tests for :class:`DelayAndSumBeamformer`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.beamforming.delay_and_sum_beamformer import DelayAndSumBeamformer
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_non_positive_num_elements(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="num_elements"):
                DelayAndSumBeamformer(
                    signal=sig,
                    num_elements=0,
                    element_spacing_m=0.05,
                    steering_angle_deg=0.0,
                    _config=KnotConfig(id="b"),
                )

    def test_rejects_non_positive_element_spacing(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="element_spacing_m"):
                DelayAndSumBeamformer(
                    signal=sig,
                    num_elements=4,
                    element_spacing_m=0.0,
                    steering_angle_deg=0.0,
                    _config=KnotConfig(id="b"),
                )

    def test_accepts_valid_params(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            DelayAndSumBeamformer(
                signal=sig,
                num_elements=8,
                element_spacing_m=0.05,
                steering_angle_deg=30.0,
                _config=KnotConfig(id="b"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_single_channel_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            DelayAndSumBeamformer(
                signal=sig,
                num_elements=4,
                element_spacing_m=0.05,
                steering_angle_deg=0.0,
                _config=KnotConfig(id="b"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["b"]
        assert isinstance(out, SignalFrame)
        assert out.channel_count == 1
        assert out.signal_id == "test:das"
        assert out.sample_rate_hz == 1000.0
