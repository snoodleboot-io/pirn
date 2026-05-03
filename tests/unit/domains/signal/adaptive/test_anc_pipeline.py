"""Unit tests for :class:`ANCPipeline`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.adaptive.anc_pipeline import ANCPipeline
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import (
    emit_reference_frame,
    emit_signal_frame,
)


class TestConstruction:
    def test_rejects_zero_step_size(self) -> None:
        with Tapestry():
            ref = emit_signal_frame(_config=KnotConfig(id="ref"))
            err = emit_reference_frame(_config=KnotConfig(id="err"))
            with pytest.raises(ValueError, match="step_size"):
                ANCPipeline(
                    reference=ref,
                    error=err,
                    step_size=0.0,
                    filter_length=32,
                    _config=KnotConfig(id="anc"),
                )

    def test_rejects_step_size_above_one(self) -> None:
        with Tapestry():
            ref = emit_signal_frame(_config=KnotConfig(id="ref"))
            err = emit_reference_frame(_config=KnotConfig(id="err"))
            with pytest.raises(ValueError, match="step_size"):
                ANCPipeline(
                    reference=ref,
                    error=err,
                    step_size=1.5,
                    filter_length=32,
                    _config=KnotConfig(id="anc"),
                )

    def test_rejects_non_positive_filter_length(self) -> None:
        with Tapestry():
            ref = emit_signal_frame(_config=KnotConfig(id="ref"))
            err = emit_reference_frame(_config=KnotConfig(id="err"))
            with pytest.raises(ValueError, match="filter_length"):
                ANCPipeline(
                    reference=ref,
                    error=err,
                    step_size=0.01,
                    filter_length=0,
                    _config=KnotConfig(id="anc"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry():
            ref = emit_signal_frame(_config=KnotConfig(id="ref"))
            err = emit_reference_frame(_config=KnotConfig(id="err"))
            anc = ANCPipeline(
                reference=ref,
                error=err,
                step_size=0.01,
                filter_length=32,
                _config=KnotConfig(id="anc"),
            )
        assert anc.step_size == 0.01
        assert anc.filter_length == 32


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            ref = emit_signal_frame(_config=KnotConfig(id="ref"))
            err = emit_reference_frame(_config=KnotConfig(id="err"))
            ANCPipeline(
                reference=ref,
                error=err,
                step_size=0.01,
                filter_length=32,
                _config=KnotConfig(id="anc"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["anc"]
        assert isinstance(out, SignalFrame)
        assert out.sample_rate_hz == 1000.0
