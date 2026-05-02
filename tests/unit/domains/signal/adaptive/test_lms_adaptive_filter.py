"""Unit tests for :class:`LMSAdaptiveFilter`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.adaptive.lms_adaptive_filter import LMSAdaptiveFilter
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
                LMSAdaptiveFilter(
                    signal=sig,
                    reference=ref,
                    filter_length=0,
                    step_size=0.01,
                    _config=KnotConfig(id="lms"),
                )

    def test_rejects_non_positive_step_size(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ref = emit_reference_frame(_config=KnotConfig(id="ref"))
            with pytest.raises(ValueError, match="step_size"):
                LMSAdaptiveFilter(
                    signal=sig,
                    reference=ref,
                    filter_length=8,
                    step_size=0,
                    _config=KnotConfig(id="lms"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ref = emit_reference_frame(_config=KnotConfig(id="ref"))
            LMSAdaptiveFilter(
                signal=sig,
                reference=ref,
                filter_length=8,
                step_size=0.01,
                _config=KnotConfig(id="lms"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["lms"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:lms"
