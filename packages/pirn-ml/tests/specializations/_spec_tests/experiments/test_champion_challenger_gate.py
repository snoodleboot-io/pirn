"""Tests for :class:`ChampionChallengerCheck`.

Renamed from ChampionChallengerGate per R9 (*Check suffix).
"""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.specializations.experiments.champion_challenger_check import (
    ChampionChallengerCheck,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.eval_report_payload import EvalReportPayload
from pirn_ml.types.model_manifest import ModelManifest
from pirn_ml.types.split_manifest import SplitManifest


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    return SplitManifest(train=train, test=test)


@knot
async def emit_champion() -> ModelManifest:
    return ModelManifest(
        model_id="champ",
        algorithm="rf",
        feature_names=("a",),
        target_name="y",
    )


@knot
async def emit_challenger() -> ModelManifest:
    return ModelManifest(
        model_id="chal",
        algorithm="xgb",
        feature_names=("a",),
        target_name="y",
    )


class TestConstruction(unittest.TestCase):
    def test_rejects_non_knot_champion(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            challenger = emit_challenger(_config=KnotConfig(id="chal"))
            with self.assertRaises(TypeError):
                ChampionChallengerCheck(
                    champion="not-a-knot",  # type: ignore[arg-type]
                    challenger=challenger,
                    split=split,
                    primary_metric="accuracy",
                    _config=KnotConfig(id="bad"),
                )


class TestProcessValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> ChampionChallengerCheck:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            champ = emit_champion(_config=KnotConfig(id="champ"))
            chal = emit_challenger(_config=KnotConfig(id="chal"))
            return ChampionChallengerCheck(
                champion=champ,
                challenger=chal,
                split=split,
                primary_metric="accuracy",
                _config=KnotConfig(id="ccc"),
            )

    async def test_rejects_empty_primary_metric(self) -> None:
        check = self._make_knot()
        with self.assertRaises(ValueError):
            await check.process(
                champion=object(),  # type: ignore[arg-type]
                challenger=object(),  # type: ignore[arg-type]
                split=object(),  # type: ignore[arg-type]
                primary_metric="",
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_comparison_with_winner_decision(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            champ = emit_champion(_config=KnotConfig(id="champ"))
            chal = emit_challenger(_config=KnotConfig(id="chal"))
            ChampionChallengerCheck(
                champion=champ,
                challenger=chal,
                split=split,
                primary_metric="accuracy",
                min_improvement=0.0,
                _config=KnotConfig(id="check"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["check"]
        assert isinstance(out, dict)
        assert "challenger_wins" in out
        assert isinstance(out["challenger_wins"], bool)
        comparison = out["comparison"]
        assert isinstance(comparison, EvalReportPayload)
        assert "champion_accuracy" in comparison.metrics.scores
        assert "challenger_accuracy" in comparison.metrics.scores
        assert "delta_accuracy" in comparison.metrics.scores
