"""Unit tests for :class:`SeizureDetector`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.eeg_meg.seizure_detector import SeizureDetector
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_signal(self) -> None:
        with pytest.raises(TypeError, match="SignalFrame"):
            SeizureDetector(
                signal="x",  # type: ignore[arg-type]
                threshold=0.5,
                _config=KnotConfig(id="s"),
            )

    def test_rejects_non_numeric_threshold(self) -> None:
        with pytest.raises(TypeError, match="threshold"):
            SeizureDetector(
                signal=SignalFrame(),
                threshold="x",  # type: ignore[arg-type]
                _config=KnotConfig(id="s"),
            )

    def test_rejects_negative_threshold(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            SeizureDetector(
                signal=SignalFrame(),
                threshold=-1.0,
                _config=KnotConfig(id="s"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_intervals(self) -> None:
        with Tapestry() as t:
            SeizureDetector(
                signal=SignalFrame(),
                threshold=0.5,
                _config=KnotConfig(id="s"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["s"]
        assert isinstance(out, tuple)
