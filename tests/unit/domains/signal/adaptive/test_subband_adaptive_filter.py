"""Unit tests for :class:`SubbandAdaptiveFilter`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.adaptive.subband_adaptive_filter import (
    SubbandAdaptiveFilter,
)
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import (
    emit_reference_frame,
    emit_signal_frame,
)


class TestConstruction:
    def test_rejects_subband_count_le_one(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ref = emit_reference_frame(_config=KnotConfig(id="ref"))
            with pytest.raises(ValueError, match="subband_count"):
                SubbandAdaptiveFilter(
                    signal=sig,
                    reference=ref,
                    subband_count=1,
                    filter_length_per_band=8,
                    step_size=0.1,
                    _config=KnotConfig(id="sb"),
                )

    def test_rejects_non_positive_filter_length_per_band(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ref = emit_reference_frame(_config=KnotConfig(id="ref"))
            with pytest.raises(ValueError, match="filter_length_per_band"):
                SubbandAdaptiveFilter(
                    signal=sig,
                    reference=ref,
                    subband_count=4,
                    filter_length_per_band=0,
                    step_size=0.1,
                    _config=KnotConfig(id="sb"),
                )

    def test_rejects_non_positive_step_size(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ref = emit_reference_frame(_config=KnotConfig(id="ref"))
            with pytest.raises(ValueError, match="step_size"):
                SubbandAdaptiveFilter(
                    signal=sig,
                    reference=ref,
                    subband_count=4,
                    filter_length_per_band=8,
                    step_size=0,
                    _config=KnotConfig(id="sb"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ref = emit_reference_frame(_config=KnotConfig(id="ref"))
            SubbandAdaptiveFilter(
                signal=sig,
                reference=ref,
                subband_count=4,
                filter_length_per_band=8,
                step_size=0.1,
                _config=KnotConfig(id="sb"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["sb"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:subband-adaptive"
