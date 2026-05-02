"""Unit tests for :class:`StepCounter`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.domains.health.wearables.step_counter import StepCounter
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_signal(self) -> None:
        with pytest.raises(TypeError, match="SignalFrame"):
            StepCounter(
                signal="x",  # type: ignore[arg-type]
                threshold=0.5,
                _config=KnotConfig(id="s"),
            )

    def test_rejects_negative_threshold(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            StepCounter(
                signal=SignalFrame(),
                threshold=-0.1,
                _config=KnotConfig(id="s"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_int(self) -> None:
        with Tapestry() as t:
            StepCounter(
                signal=SignalFrame(),
                threshold=1.0,
                _config=KnotConfig(id="s"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["s"]
        assert isinstance(out, int)
