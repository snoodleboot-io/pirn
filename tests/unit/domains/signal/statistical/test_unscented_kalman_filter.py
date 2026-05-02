"""Unit tests for :class:`UnscentedKalmanFilter`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.statistical.unscented_kalman_filter import (
    UnscentedKalmanFilter,
)
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_non_positive_state_dim(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="state_dim"):
                UnscentedKalmanFilter(
                    signal=sig,
                    state_dim=0,
                    observation_dim=1,
                    _config=KnotConfig(id="ukf"),
                )

    def test_rejects_non_positive_observation_dim(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="observation_dim"):
                UnscentedKalmanFilter(
                    signal=sig,
                    state_dim=2,
                    observation_dim=0,
                    _config=KnotConfig(id="ukf"),
                )

    def test_rejects_non_positive_alpha(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="alpha"):
                UnscentedKalmanFilter(
                    signal=sig,
                    state_dim=2,
                    observation_dim=1,
                    alpha=0,
                    _config=KnotConfig(id="ukf"),
                )

    def test_rejects_non_numeric_beta(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(TypeError, match="beta"):
                UnscentedKalmanFilter(
                    signal=sig,
                    state_dim=2,
                    observation_dim=1,
                    beta="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="ukf"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            UnscentedKalmanFilter(
                signal=sig,
                state_dim=2,
                observation_dim=1,
                _config=KnotConfig(id="ukf"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["ukf"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:ukf"
