"""Unit tests for :class:`RiskBasedInspectionScorer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn_oilgas.integrity.risk_based_inspection_scorer import (
    RiskBasedInspectionScorer,
)

_CORROSION: dict[str, float] = {"max_rate_mpy": 5.0, "mean_rate_mpy": 1.0, "feature_count": 3.0}


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, consequence_score: float = 0.5) -> RiskBasedInspectionScorer:
        return RiskBasedInspectionScorer(
            corrosion_assessment=None,  # type: ignore[arg-type]
            consequence_score=consequence_score,
            _config=KnotConfig(id="rbi", validate_io=False),
        )

    async def test_rejects_non_numeric_consequence(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "consequence_score"):
            await knot.process(corrosion_assessment=_CORROSION, consequence_score="x")  # type: ignore[arg-type]

    async def test_rejects_out_of_range(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, r"\[0, 1\]"):
            await knot.process(corrosion_assessment=_CORROSION, consequence_score=2.0)

    async def test_returns_risk_score(self) -> None:
        knot = self._make_knot(consequence_score=0.5)
        out = await knot.process(corrosion_assessment=_CORROSION, consequence_score=0.5)
        assert out["consequence"] == 0.5
        assert "risk_score" in out
