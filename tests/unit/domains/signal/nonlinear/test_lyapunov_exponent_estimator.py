"""Unit tests for :class:`LyapunovExponentEstimator`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.nonlinear.lyapunov_exponent_estimator import (
    LyapunovExponentEstimator,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_non_positive_embedding_dim(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="embedding_dim"):
                LyapunovExponentEstimator(
                    signal=sig,
                    embedding_dim=0,
                    time_delay=1,
                    _config=KnotConfig(id="l"),
                )

    def test_rejects_non_positive_time_delay(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="time_delay"):
                LyapunovExponentEstimator(
                    signal=sig,
                    embedding_dim=2,
                    time_delay=0,
                    _config=KnotConfig(id="l"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_estimator_dict(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            LyapunovExponentEstimator(
                signal=sig,
                embedding_dim=3,
                time_delay=1,
                _config=KnotConfig(id="l"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["l"]
        assert out["estimator"] == "lyapunov"
        assert out["embedding_dim"] == 3
