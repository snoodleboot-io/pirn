"""Unit tests for :class:`RiskBasedInspectionScorer`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.integrity.risk_based_inspection_scorer import (
    RiskBasedInspectionScorer,
)
from pirn.tapestry import Tapestry


class _CorrosionSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, float]:
        return {"max_rate_mpy": 5.0, "mean_rate_mpy": 1.0, "feature_count": 3.0}


class TestConstruction(unittest.TestCase):
    def test_rejects_non_numeric_consequence(self) -> None:
        with self.assertRaisesRegex(TypeError, "consequence_score"):
            with Tapestry():
                src = _CorrosionSource(_config=KnotConfig(id="src"))
                RiskBasedInspectionScorer(
                    corrosion_assessment=src,
                    consequence_score="x",  # type: ignore[arg-type]
                    _config=KnotConfig(id="rbi"),
                )

    def test_rejects_out_of_range(self) -> None:
        with self.assertRaisesRegex(ValueError, r"\[0, 1\]"):
            with Tapestry():
                src = _CorrosionSource(_config=KnotConfig(id="src"))
                RiskBasedInspectionScorer(
                    corrosion_assessment=src,
                    consequence_score=2.0,
                    _config=KnotConfig(id="rbi"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_risk_score(self) -> None:
        with Tapestry() as t:
            src = _CorrosionSource(_config=KnotConfig(id="src"))
            RiskBasedInspectionScorer(
                corrosion_assessment=src,
                consequence_score=0.5,
                _config=KnotConfig(id="rbi"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["rbi"]
        assert out["consequence"] == 0.5
        assert "risk_score" in out
