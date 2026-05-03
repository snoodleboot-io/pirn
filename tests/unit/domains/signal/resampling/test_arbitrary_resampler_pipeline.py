"""Unit tests for :class:`ArbitraryResamplerPipeline`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.resampling.arbitrary_resampler_pipeline import ArbitraryResamplerPipeline
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_non_positive_input_rate(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="input_rate_hz"):
                ArbitraryResamplerPipeline(
                    signal=sig,
                    input_rate_hz=0.0,
                    output_rate_hz=16000.0,
                    _config=KnotConfig(id="ar"),
                )

    def test_rejects_non_positive_output_rate(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="output_rate_hz"):
                ArbitraryResamplerPipeline(
                    signal=sig,
                    input_rate_hz=8000.0,
                    output_rate_hz=-1.0,
                    _config=KnotConfig(id="ar"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ar = ArbitraryResamplerPipeline(
                signal=sig,
                input_rate_hz=8000.0,
                output_rate_hz=16000.0,
                _config=KnotConfig(id="ar"),
            )
        assert ar.input_rate_hz == 8000.0
        assert ar.output_rate_hz == 16000.0


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_resampled_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ArbitraryResamplerPipeline(
                signal=sig,
                input_rate_hz=1000.0,
                output_rate_hz=2000.0,
                _config=KnotConfig(id="ar"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["ar"]
        assert isinstance(out, SignalFrame)
        assert out.sample_rate_hz == 2000.0
