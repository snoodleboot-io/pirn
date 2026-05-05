"""Unit tests for :class:`RodPumpOptimizer`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.production.rod_pump_optimizer import RodPumpOptimizer
from pirn.tapestry import Tapestry


class _CardSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {
            "surface_load_lbf": [1000.0, 2000.0, 3000.0],
            "surface_position_in": [0.0, 72.0, 144.0],
            "current_spm": 8.0,
            "stroke_length_in": 144.0,
        }


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_fillage_pct(self) -> None:
        with self.assertRaisesRegex(ValueError, "target_fillage_pct"):
            with Tapestry():
                src = _CardSource(_config=KnotConfig(id="src"))
                RodPumpOptimizer(
                    dynagraph_card=src,
                    target_fillage_pct=0.0,
                    max_spm=10.0,
                    _config=KnotConfig(id="rpo"),
                )

    def test_rejects_non_positive_max_spm(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_spm"):
            with Tapestry():
                src = _CardSource(_config=KnotConfig(id="src"))
                RodPumpOptimizer(
                    dynagraph_card=src,
                    target_fillage_pct=80.0,
                    max_spm=0.0,
                    _config=KnotConfig(id="rpo"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_recommendation(self) -> None:
        with Tapestry() as t:
            src = _CardSource(_config=KnotConfig(id="src"))
            RodPumpOptimizer(
                dynagraph_card=src,
                target_fillage_pct=80.0,
                max_spm=10.0,
                _config=KnotConfig(id="rpo"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["rpo"]
        assert "recommended_spm" in out
        assert "recommended_stroke_in" in out
        assert out["fillage_pct"] == 80.0
