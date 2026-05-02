"""Unit tests for :class:`BesselFilter`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.filters.bessel_filter import BesselFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_non_positive_order(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="positive integer"):
                BesselFilter(
                    signal=sig,
                    order=0,
                    cutoff_hz=10.0,
                    _config=KnotConfig(id="b"),
                )

    def test_rejects_non_positive_cutoff(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="cutoff_hz"):
                BesselFilter(
                    signal=sig,
                    order=4,
                    cutoff_hz=0,
                    _config=KnotConfig(id="b"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            BesselFilter(
                signal=sig,
                order=4,
                cutoff_hz=50.0,
                _config=KnotConfig(id="b"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["b"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:bessel"
