"""Unit tests for :class:`HighPassFilter`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.filters.high_pass_filter import HighPassFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_non_positive_cutoff(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="cutoff_hz"):
                HighPassFilter(
                    signal=sig,
                    cutoff_hz=0,
                    _config=KnotConfig(id="hp"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            HighPassFilter(
                signal=sig,
                cutoff_hz=10.0,
                _config=KnotConfig(id="hp"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["hp"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:highpass"
