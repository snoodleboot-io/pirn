"""Unit tests for :class:`SavitzkyGolayFilter`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.filters.savitzky_golay_filter import SavitzkyGolayFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_non_positive_window_length(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="positive integer"):
                SavitzkyGolayFilter(
                    signal=sig,
                    window_length=0,
                    polynomial_order=2,
                    _config=KnotConfig(id="sg"),
                )

    def test_rejects_even_window_length(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="odd"):
                SavitzkyGolayFilter(
                    signal=sig,
                    window_length=10,
                    polynomial_order=2,
                    _config=KnotConfig(id="sg"),
                )

    def test_rejects_negative_polynomial_order(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="non-negative"):
                SavitzkyGolayFilter(
                    signal=sig,
                    window_length=11,
                    polynomial_order=-1,
                    _config=KnotConfig(id="sg"),
                )

    def test_rejects_polynomial_order_ge_window_length(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="< window_length"):
                SavitzkyGolayFilter(
                    signal=sig,
                    window_length=11,
                    polynomial_order=11,
                    _config=KnotConfig(id="sg"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            SavitzkyGolayFilter(
                signal=sig,
                window_length=11,
                polynomial_order=2,
                _config=KnotConfig(id="sg"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["sg"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:savgol"
