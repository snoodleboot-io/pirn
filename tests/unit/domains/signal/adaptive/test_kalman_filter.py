"""Unit tests for :class:`KalmanFilter`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.adaptive.kalman_filter import KalmanFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_non_positive_state_dim(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="state_dim"):
                KalmanFilter(
                    signal=sig,
                    state_dim=0,
                    observation_dim=1,
                    _config=KnotConfig(id="k"),
                )

    def test_rejects_non_positive_observation_dim(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="observation_dim"):
                KalmanFilter(
                    signal=sig,
                    state_dim=2,
                    observation_dim=0,
                    _config=KnotConfig(id="k"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            KalmanFilter(
                signal=sig,
                state_dim=2,
                observation_dim=1,
                _config=KnotConfig(id="k"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["k"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:kalman"
