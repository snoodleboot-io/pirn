"""Unit tests for :class:`MonteCarloSimulator`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.reservoir.monte_carlo_simulator import MonteCarloSimulator
from pirn.tapestry import Tapestry


class _DeterministicSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> float:
        return 100.0


class TestConstruction:
    def test_rejects_non_positive_trial_count(self) -> None:
        with pytest.raises(ValueError, match="trial_count"):
            with Tapestry():
                src = _DeterministicSource(_config=KnotConfig(id="src"))
                MonteCarloSimulator(
                    deterministic_estimate=src,
                    trial_count=0,
                    _config=KnotConfig(id="mc"),
                )

    def test_rejects_non_int_seed(self) -> None:
        with pytest.raises(TypeError, match="seed"):
            with Tapestry():
                src = _DeterministicSource(_config=KnotConfig(id="src"))
                MonteCarloSimulator(
                    deterministic_estimate=src,
                    trial_count=10,
                    seed="x",  # type: ignore[arg-type]
                    _config=KnotConfig(id="mc"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_percentiles(self) -> None:
        with Tapestry() as t:
            src = _DeterministicSource(_config=KnotConfig(id="src"))
            MonteCarloSimulator(
                deterministic_estimate=src,
                trial_count=100,
                _config=KnotConfig(id="mc"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["mc"]
        assert out["p50"] == 100.0
        assert out["p10"] == 70.0
        assert out["p90"] == 130.0
