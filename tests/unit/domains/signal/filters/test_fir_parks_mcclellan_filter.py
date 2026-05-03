"""Unit tests for :class:`FIRParksMcClellanFilter`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.filters.fir_parks_mcclellan_filter import FIRParksMcClellanFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_even_num_taps(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="positive odd"):
                FIRParksMcClellanFilter(
                    signal=sig,
                    num_taps=32,
                    bands=(0.0, 0.4, 0.6, 1.0),
                    desired=(1.0, 0.0),
                    _config=KnotConfig(id="f"),
                )

    def test_rejects_zero_num_taps(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="positive odd"):
                FIRParksMcClellanFilter(
                    signal=sig,
                    num_taps=0,
                    bands=(0.0, 0.4, 0.6, 1.0),
                    desired=(1.0, 0.0),
                    _config=KnotConfig(id="f"),
                )

    def test_rejects_odd_length_bands(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="bands"):
                FIRParksMcClellanFilter(
                    signal=sig,
                    num_taps=31,
                    bands=(0.0, 0.4, 0.6),
                    desired=(1.0,),
                    _config=KnotConfig(id="f"),
                )

    def test_rejects_mismatched_desired(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="desired"):
                FIRParksMcClellanFilter(
                    signal=sig,
                    num_taps=31,
                    bands=(0.0, 0.4, 0.6, 1.0),
                    desired=(1.0,),
                    _config=KnotConfig(id="f"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            FIRParksMcClellanFilter(
                signal=sig,
                num_taps=31,
                bands=(0.0, 0.4, 0.6, 1.0),
                desired=(1.0, 0.0),
                _config=KnotConfig(id="f"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["f"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:fir-pm"
