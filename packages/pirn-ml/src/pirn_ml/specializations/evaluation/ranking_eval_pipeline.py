"""``RankingEvalPipeline`` — SubTapestry for ranking model evaluation.

Computes NDCG@k, MRR, and MAP@k for a ranking model on a held-out split.

Algorithm:
    1. Receive ``model`` (ModelManifest), ``split`` (SplitManifest), and ``k`` (int) via process().
    2. Validate k is an int >= 1.
    3. Wire an inner Tapestry with Evaluator using NDCG@k, MRR, MAP@k metrics.
    4. Run the inner Tapestry via _run_inner() and return the EvalMetadata.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_ml.evaluation.evaluator import Evaluator
from pirn_ml.types.model_manifest import ModelManifest
from pirn_ml.types.split_manifest import SplitManifest


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
        k: Knot | int = 10,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(model=model, split=split, k=k, _config=_config, **kwargs)

    async def process(
        self,
        model: ModelManifest,
        split: SplitManifest,
        k: int = 10,
        **_: Any,
    ) -> Any:
        """Evaluate the ranking model with NDCG@k, MRR, and MAP@k and return the resulting EvalMetadata.

        Args:
            model: ModelManifest reference to evaluate.
            split: SplitManifest whose test partition is used for ranking metrics.
            k: Cut-off rank; must be an int >= 1.

        Returns:
            EvalReportPayload containing ndcg_at_k, mrr, and map_at_k metrics.

        Raises:
            ValueError: If k is not a valid int >= 1.
        """
        if not isinstance(k, int):
            raise TypeError("RankingEvalPipeline: k must be an int")
        if k < 1:
            raise ValueError("RankingEvalPipeline: k must be >= 1")
        metrics = (
            f"ndcg_at_{k}",
            "mrr",
            f"map_at_{k}",
        )
        model_node = _emit_value(value=model, _config=KnotConfig(id="model"))
        split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
        return Evaluator(
            model=model_node,
            split=split_node,
            metrics=metrics,
            _config=KnotConfig(id="evaluate"),
        )
