"""``RankingEvalPipeline`` — SubTapestry for ranking model evaluation.

Computes NDCG@k, MRR, and MAP@k for a ranking model on a held-out split.
"""

from __future__ import annotations

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


class RankingEvalPipeline(SubTapestry):
    """Evaluate a ranking model with NDCG@k, MRR, and MAP@k."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        k: int = 10,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(model, Knot):
            raise TypeError("RankingEvalPipeline: model must be a Knot")
        if not isinstance(split, Knot):
            raise TypeError("RankingEvalPipeline: split must be a Knot")
        if not isinstance(k, int):
            raise TypeError("RankingEvalPipeline: k must be an int")
        if k < 1:
            raise ValueError("RankingEvalPipeline: k must be >= 1")
        self._k = k
        super().__init__(model=model, split=split, _config=_config, **kwargs)

    @property
    def k(self) -> int:
        return self._k

    async def process(
        self, model: TrainedModel, split: DataSplit, **_: Any
    ) -> EvalReport:
        metrics = (
            f"ndcg_at_{self._k}",
            "mrr",
            f"map_at_{self._k}",
        )
        with Tapestry() as inner:
            model_node = _emit_value(
                value=model, _config=KnotConfig(id="model")
            )
            split_node = _emit_value(
                value=split, _config=KnotConfig(id="split")
            )
            Evaluator(
                model=model_node,
                split=split_node,
                metrics=metrics,
                _config=KnotConfig(id="evaluate"),
            )
        inner_result = await self._run_inner(inner)
        return inner_result.outputs["evaluate"]
