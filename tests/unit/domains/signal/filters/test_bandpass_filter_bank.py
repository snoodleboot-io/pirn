"""Unit tests for :class:`BandpassFilterBank`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.filters.bandpass_filter_bank import BandpassFilterBank
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_empty_bands(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="bands"):
                BandpassFilterBank(
                    signal=sig, bands=(), order=4, _config=KnotConfig(id="fb")
                )

    def test_rejects_invalid_band_pair(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="bands"):
                BandpassFilterBank(
                    signal=sig, bands=((100.0,),), order=4, _config=KnotConfig(id="fb")  # type: ignore[arg-type]
                )

    def test_rejects_inverted_band_bounds(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="0 < low_hz < high_hz"):
                BandpassFilterBank(
                    signal=sig,
                    bands=((500.0, 100.0),),
                    order=4,
                    _config=KnotConfig(id="fb"),
                )

    def test_rejects_non_positive_order(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="positive integer"):
                BandpassFilterBank(
                    signal=sig,
                    bands=((100.0, 200.0),),
                    order=0,
                    _config=KnotConfig(id="fb"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_list_of_signal_frames(self) -> None:
        bands = ((100.0, 200.0), (300.0, 400.0), (500.0, 600.0))
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            BandpassFilterBank(
                signal=sig, bands=bands, order=4, _config=KnotConfig(id="fb")
            )
        result = await t.run(RunRequest())
        out = result.outputs["fb"]
        assert isinstance(out, list)
        assert len(out) == 3
        assert all(isinstance(f, SignalFrame) for f in out)
