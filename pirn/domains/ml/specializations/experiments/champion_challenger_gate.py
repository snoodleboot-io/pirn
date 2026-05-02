"""``ChampionChallengerGate`` — compare a challenger model against the
current champion on a shared test split and gate downstream by an
improvement threshold on a primary metric.

The gate evaluates both models with the same metric set on the same
:class:`DataSplit`, then returns:

* ``challenger_wins``: boolean — ``True`` when
  ``challenger.metrics[primary_metric] - champion.metrics[primary_metric]
  >= min_improvement``.
* ``comparison``: a synthetic :class:`EvalReport` whose ``metrics`` map
  reports ``champion_<metric>``, ``challenger_<metric>``, and
  ``delta_<metric>`` for every metric scored.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class ChampionChallengerGate(SubTapestry):
    """Evaluate champion vs challenger; gate by primary-metric improvement."""

    def __init__(
        self,
        *,
        champion: Knot,
        challenger: Knot,
        split: Knot,
        primary_metric: str,
        min_improvement: float = 0.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(champion, Knot):
            raise TypeError(
                "ChampionChallengerGate: champion must be a Knot"
            )
        if not isinstance(challenger, Knot):
            raise TypeError(
                "ChampionChallengerGate: challenger must be a Knot"
            )
        if not isinstance(split, Knot):
            raise TypeError(
                "ChampionChallengerGate: split must be a Knot"
            )
        if not isinstance(primary_metric, str) or not primary_metric:
            raise ValueError(
                "ChampionChallengerGate: primary_metric must be a non-empty "
                "string"
            )
        if not isinstance(min_improvement, (int, float)):
            raise TypeError(
                "ChampionChallengerGate: min_improvement must be a number"
            )
        self._primary_metric = primary_metric
        self._min_improvement = float(min_improvement)
        super().__init__(
            champion=champion,
            challenger=challenger,
            split=split,
            _config=_config,
            **kwargs,
        )

    @property
    def primary_metric(self) -> str:
        return self._primary_metric

    @property
    def min_improvement(self) -> float:
        return self._min_improvement

    async def process(
        self,
        champion: TrainedModel,
        challenger: TrainedModel,
        split: DataSplit,
        **_: Any,
    ) -> dict[str, Any]:
        with Tapestry() as inner:
            champion_node = _emit_value(
                value=champion, _config=KnotConfig(id="champion")
            )
            challenger_node = _emit_value(
                value=challenger, _config=KnotConfig(id="challenger")
            )
            split_node = _emit_value(
                value=split, _config=KnotConfig(id="split")
            )
            Evaluator(
                model=champion_node,
                split=split_node,
                metrics=(self._primary_metric,),
                _config=KnotConfig(id="evaluate_champion"),
            )
            Evaluator(
                model=challenger_node,
                split=split_node,
                metrics=(self._primary_metric,),
                _config=KnotConfig(id="evaluate_challenger"),
            )
        inner_result = await self._run_inner(inner)
        champion_report = inner_result.outputs["evaluate_champion"]
        challenger_report = inner_result.outputs["evaluate_challenger"]
        if not isinstance(champion_report, EvalReport):
            raise TypeError(
                "ChampionChallengerGate: champion evaluator did not return "
                "an EvalReport"
            )
        if not isinstance(challenger_report, EvalReport):
            raise TypeError(
                "ChampionChallengerGate: challenger evaluator did not return "
                "an EvalReport"
            )
        champion_score = float(
            champion_report.metrics[self._primary_metric]
        )
        challenger_score = float(
            challenger_report.metrics[self._primary_metric]
        )
        delta = challenger_score - champion_score
        challenger_wins = delta >= self._min_improvement
        comparison_metrics: dict[str, float] = {
            f"champion_{self._primary_metric}": champion_score,
            f"challenger_{self._primary_metric}": challenger_score,
            f"delta_{self._primary_metric}": delta,
        }
        comparison = EvalReport(
            model_id=challenger.model_id,
            dataset_name=split.test.name,
            metrics=MappingProxyType(comparison_metrics),
            details=MappingProxyType(
                {
                    "primary_metric": self._primary_metric,
                    "min_improvement": self._min_improvement,
                    "champion_model_id": champion.model_id,
                    "challenger_model_id": challenger.model_id,
                    "challenger_wins": challenger_wins,
                }
            ),
            evaluated_at=datetime.now(timezone.utc),
        )
        return {
            "challenger_wins": challenger_wins,
            "comparison": comparison,
        }
