"""Unit tests for :class:`AffineProjectionFilter`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.adaptive.affine_projection_filter import (
    AffineProjectionFilter,
)
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import (
    emit_reference_frame,
    emit_signal_frame,
)


class TestConstruction:
    def test_rejects_non_positive_filter_length(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ref = emit_reference_frame(_config=KnotConfig(id="ref"))
            with pytest.raises(ValueError, match="filter_length"):
                AffineProjectionFilter(
                    signal=sig,
                    reference=ref,
                    filter_length=0,
                    projection_order=2,
                    step_size=0.1,
                    _config=KnotConfig(id="apa"),
                )

    def test_rejects_non_positive_projection_order(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ref = emit_reference_frame(_config=KnotConfig(id="ref"))
            with pytest.raises(ValueError, match="projection_order"):
                AffineProjectionFilter(
                    signal=sig,
                    reference=ref,
                    filter_length=8,
                    projection_order=0,
                    step_size=0.1,
                    _config=KnotConfig(id="apa"),
                )

    def test_rejects_non_positive_step_size(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ref = emit_reference_frame(_config=KnotConfig(id="ref"))
            with pytest.raises(ValueError, match="step_size"):
                AffineProjectionFilter(
                    signal=sig,
                    reference=ref,
                    filter_length=8,
                    projection_order=2,
                    step_size=0,
                    _config=KnotConfig(id="apa"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ref = emit_reference_frame(_config=KnotConfig(id="ref"))
            AffineProjectionFilter(
                signal=sig,
                reference=ref,
                filter_length=8,
                projection_order=2,
                step_size=0.1,
                _config=KnotConfig(id="apa"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["apa"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:apa"
