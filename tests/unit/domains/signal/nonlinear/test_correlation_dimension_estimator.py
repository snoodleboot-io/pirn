"""Unit tests for :class:`CorrelationDimensionEstimator`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.nonlinear.correlation_dimension_estimator import (
    CorrelationDimensionEstimator,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_non_positive_embedding_dim(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="embedding_dim"):
                CorrelationDimensionEstimator(
                    signal=sig,
                    embedding_dim=0,
                    radius_min=0.01,
                    radius_max=0.1,
                    _config=KnotConfig(id="c"),
                )

    def test_rejects_non_positive_radius_min(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="radius_min"):
                CorrelationDimensionEstimator(
                    signal=sig,
                    embedding_dim=5,
                    radius_min=0,
                    radius_max=0.1,
                    _config=KnotConfig(id="c"),
                )

    def test_rejects_radius_max_le_radius_min(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="radius_max"):
                CorrelationDimensionEstimator(
                    signal=sig,
                    embedding_dim=5,
                    radius_min=0.5,
                    radius_max=0.5,
                    _config=KnotConfig(id="c"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_estimator_dict(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            CorrelationDimensionEstimator(
                signal=sig,
                embedding_dim=5,
                radius_min=0.01,
                radius_max=0.5,
                _config=KnotConfig(id="c"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["c"]
        assert out["estimator"] == "correlation_dimension"
