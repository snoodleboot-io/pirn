"""Unit tests for :class:`AllpassFilter`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.filters.allpass_filter import AllpassFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_pole_radius_zero(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="pole_radius"):
                AllpassFilter(signal=sig, pole_radius=0.0, _config=KnotConfig(id="f"))

    def test_rejects_pole_radius_one(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="pole_radius"):
                AllpassFilter(signal=sig, pole_radius=1.0, _config=KnotConfig(id="f"))

    def test_rejects_pole_radius_negative(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="pole_radius"):
                AllpassFilter(signal=sig, pole_radius=-0.5, _config=KnotConfig(id="f"))

    def test_accepts_valid_pole_radius(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            AllpassFilter(signal=sig, pole_radius=0.9, _config=KnotConfig(id="f"))


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            AllpassFilter(signal=sig, pole_radius=0.5, _config=KnotConfig(id="f"))
        result = await t.run(RunRequest())
        out = result.outputs["f"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:allpass"
        assert out.sample_rate_hz == 1000.0
