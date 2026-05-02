"""Unit tests for :class:`WienerFilter`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.filters.wiener_filter import WienerFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_non_positive_window_size(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="window_size"):
                WienerFilter(
                    signal=sig,
                    window_size=0,
                    _config=KnotConfig(id="w"),
                )

    def test_rejects_non_positive_noise_power(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="noise_power"):
                WienerFilter(
                    signal=sig,
                    window_size=5,
                    noise_power=0,
                    _config=KnotConfig(id="w"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            WienerFilter(
                signal=sig,
                window_size=5,
                _config=KnotConfig(id="w"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["w"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:wiener"
