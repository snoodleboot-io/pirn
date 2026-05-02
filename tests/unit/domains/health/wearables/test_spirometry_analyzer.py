"""Unit tests for :class:`SpirometryAnalyzer`."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.wearables.spirometry_analyzer import (
    SpirometryAnalyzer,
)
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_sequence(self) -> None:
        with pytest.raises(TypeError, match="flow_l_per_sec"):
            SpirometryAnalyzer(
                flow_l_per_sec=42,  # type: ignore[arg-type]
                sample_rate_hz=100.0,
                _config=KnotConfig(id="s"),
            )

    def test_rejects_non_numeric_flow(self) -> None:
        with pytest.raises(TypeError, match="numeric"):
            SpirometryAnalyzer(
                flow_l_per_sec=["x"],  # type: ignore[list-item]
                sample_rate_hz=100.0,
                _config=KnotConfig(id="s"),
            )

    def test_rejects_non_positive_rate(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            SpirometryAnalyzer(
                flow_l_per_sec=[],
                sample_rate_hz=0.0,
                _config=KnotConfig(id="s"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_metric_mapping(self) -> None:
        with Tapestry() as t:
            SpirometryAnalyzer(
                flow_l_per_sec=[1.0, 2.0, 3.0],
                sample_rate_hz=100.0,
                _config=KnotConfig(id="s"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["s"]
        assert isinstance(out, Mapping)
        assert "fev1_l" in out
