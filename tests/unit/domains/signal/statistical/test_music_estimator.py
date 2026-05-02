"""Unit tests for :class:`MUSICEstimator`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.statistical.music_estimator import MUSICEstimator
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_non_positive_subspace_dim(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="signal_subspace_dim"):
                MUSICEstimator(
                    signal=sig,
                    signal_subspace_dim=0,
                    frequency_grid_size=128,
                    _config=KnotConfig(id="m"),
                )

    def test_rejects_non_positive_grid_size(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="frequency_grid_size"):
                MUSICEstimator(
                    signal=sig,
                    signal_subspace_dim=2,
                    frequency_grid_size=0,
                    _config=KnotConfig(id="m"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_estimator_dict(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            MUSICEstimator(
                signal=sig,
                signal_subspace_dim=2,
                frequency_grid_size=128,
                _config=KnotConfig(id="m"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["m"]
        assert out["estimator"] == "music"
        assert out["frequency_grid_size"] == 128
