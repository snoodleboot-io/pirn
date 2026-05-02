"""Unit tests for :class:`Upsampler`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.resampling.upsampler import Upsampler
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_upsample_factor_le_one(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="upsample_factor"):
                Upsampler(
                    signal=sig,
                    upsample_factor=1,
                    _config=KnotConfig(id="u"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            Upsampler(
                signal=sig,
                upsample_factor=4,
                _config=KnotConfig(id="u"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["u"]
        assert isinstance(out, SignalFrame)
        assert out.sample_rate_hz == 4000.0
        assert out.samples_per_channel == 4096
