"""Unit tests for :class:`PolyphaseDecimator`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.filters.polyphase_decimator import PolyphaseDecimator
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_decimation_factor_le_one(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="decimation_factor"):
                PolyphaseDecimator(
                    signal=sig,
                    decimation_factor=1,
                    filter_taps=8,
                    _config=KnotConfig(id="pd"),
                )

    def test_rejects_non_positive_filter_taps(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="filter_taps"):
                PolyphaseDecimator(
                    signal=sig,
                    decimation_factor=4,
                    filter_taps=0,
                    _config=KnotConfig(id="pd"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_decimated_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            PolyphaseDecimator(
                signal=sig,
                decimation_factor=4,
                filter_taps=16,
                _config=KnotConfig(id="pd"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["pd"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:polyphase-dec"
        assert out.sample_rate_hz == 250.0
        assert out.samples_per_channel == 256
