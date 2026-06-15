"""``ChampionChallengerCheck`` — compare a challenger model against the
current champion on a shared test split and check downstream by an
improvement threshold on a primary metric.

The check evaluates both models with the same metric set on the same
:class:`SplitManifest`, then returns:

* ``challenger_wins``: boolean — ``True`` when
  ``challenger.metrics[primary_metric] - champion.metrics[primary_metric]
  >= min_improvement``.
* ``comparison``: a synthetic :class:`EvalMetadata` whose ``metrics`` map
  reports ``champion_<metric>``, ``challenger_<metric>``, and
  ``delta_<metric>`` for every metric scored.

Algorithm:
    1. Receive ``champion`` (ModelManifest), ``challenger`` (ModelManifest),
       ``split`` (SplitManifest), ``primary_metric`` (str), and
       ``min_improvement`` (float) via process().
    2. Validate primary_metric and min_improvement.
    3. Wire two Evaluator knots (one per model) in an inner Tapestry.
    4. Run via _run_inner(), compute delta, and return comparison report.

Math:
    delta = challenger.metrics[primary_metric] - champion.metrics[primary_metric]
    challenger_wins = (delta >= min_improvement)

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_ml.evaluation.evaluator import Evaluator
from pirn_ml.types.eval_metadata import EvalMetadata
from pirn_ml.types.eval_metrics import EvalMetrics
from pirn_ml.types.eval_report_payload import EvalReportPayload
from pirn_ml.types.model_manifest import ModelManifest
from pirn_ml.types.split_manifest import SplitManifest


@knot
async def _emit_value(value: Any) -> Any:
    return value


@knot
async def _build_champion_challenger_result(
    champion_report: EvalReportPayload,
    challenger_report: EvalReportPayload,
    champion: ModelManifest,
    challenger: ModelManifest,
    split: SplitManifest,
    primary_metric: str,
    min_imp: float,
) -> dict[str, Any]:
    champion_score = float(champion_report.metrics.scores[primary_metric])
    challenger_score = float(challenger_report.metrics.scores[primary_metric])
    delta = challenger_score - champion_score
    challenger_wins = delta >= min_imp
    comparison_metrics: dict[str, float] = {
        f"champion_{primary_metric}": champion_score,
        f"challenger_{primary_metric}": challenger_score,
        f"delta_{primary_metric}": delta,
    }
    comparison = EvalReportPayload(
        metadata=EvalMetadata(
            model_id=challenger.model_id,
            dataset_name=split.test.name,
            evaluated_at=datetime.now(UTC),
        ),
        data=EvalMetrics(
            scores=MappingProxyType(comparison_metrics),
            details=MappingProxyType(
                {
                    "primary_metric": primary_metric,
                    "min_improvement": min_imp,
                    "champion_model_id": champion.model_id,
                    "challenger_model_id": challenger.model_id,
                    "challenger_wins": challenger_wins,
                }
            ),
        ),
    )
    return {"challenger_wins": challenger_wins, "comparison": comparison}


class ChampionChallengerCheck(SubTapestry):
    """Evaluate champion vs challenger; check by primary-metric improvement."""

    def __init__(
        self,
        *,
        champion: Knot,
        challenger: Knot,
        split: Knot,
        primary_metric: Knot | str,
        min_improvement: Knot | float = 0.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            champion=champion,
            challenger=challenger,
            split=split,
            primary_metric=primary_metric,
            min_improvement=min_improvement,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        champion: ModelManifest,
        challenger: ModelManifest,
        split: SplitManifest,
        primary_metric: str = "",
        min_improvement: float = 0.0,
        **_: Any,
    ) -> Any:
        """Evaluate both models on the split and return a comparison dict indicating whether the challenger wins.

        Args:
            champion: ModelManifest reference for the current champion.
            challenger: ModelManifest reference for the new challenger.
            split: SplitManifest whose test partition is used for both evaluations.
            primary_metric: Non-empty metric name to compare.
            min_improvement: Minimum delta for challenger to win; must be numeric.

        Returns:
            Dict with ``challenger_wins`` (bool) and ``comparison`` (EvalMetadata with delta metrics).

        Raises:
            ValueError: If primary_metric is empty.
            TypeError: If min_improvement is not numeric or evaluators return unexpected types.
        """
        if not isinstance(primary_metric, str) or not primary_metric:
            raise ValueError("ChampionChallengerCheck: primary_metric must be a non-empty string")
        if not isinstance(min_improvement, (int, float)):
            raise TypeError("ChampionChallengerCheck: min_improvement must be a number")
        min_imp = float(min_improvement)
        champion_node = _emit_value(value=champion, _config=KnotConfig(id="champion"))
        challenger_node = _emit_value(value=challenger, _config=KnotConfig(id="challenger"))
        split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
        evaluated_champion = Evaluator(
            model=champion_node,
            split=split_node,
            metrics=(primary_metric,),
            _config=KnotConfig(id="evaluate_champion"),
        )
        evaluated_challenger = Evaluator(
            model=challenger_node,
            split=split_node,
            metrics=(primary_metric,),
            _config=KnotConfig(id="evaluate_challenger"),
        )
        min_imp_node = _emit_value(value=min_imp, _config=KnotConfig(id="min_imp"))
        primary_metric_node = _emit_value(
            value=primary_metric, _config=KnotConfig(id="primary_metric")
        )
        return _build_champion_challenger_result(
            champion_report=evaluated_champion,
            challenger_report=evaluated_challenger,
            champion=champion_node,
            challenger=challenger_node,
            split=split_node,
            primary_metric=primary_metric_node,
            min_imp=min_imp_node,
            _config=KnotConfig(id="combine"),
        )
