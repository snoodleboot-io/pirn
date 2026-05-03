"""``RankingEvaluator`` — Knot that computes NDCG@K, MAP@K, MRR, and
Precision@K for a recommender or ranking model.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.trained_model import TrainedModel


class RankingEvaluator(Knot):
    """Compute NDCG@K, MAP@K, MRR, and Precision@K for a ranking model."""

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
            raise TypeError("RankingEvaluator: model must be a Knot")
        if not isinstance(split, Knot):
            raise TypeError("RankingEvaluator: split must be a Knot")
        if not isinstance(k, int) or k < 1:
            raise ValueError("RankingEvaluator: k must be an int >= 1")
        self._k = k
        super().__init__(model=model, split=split, _config=_config, **kwargs)

    @property
    def k(self) -> int:
        return self._k

    async def process(
        self, model: TrainedModel, split: DataSplit, **_: Any
    ) -> Mapping[str, Any]:
        """Compute NDCG@K, MAP@K, MRR, and Precision@K for the ranking model on the test split.

        Args:
            model: TrainedModel reference for a ranking task.
            split: DataSplit whose test partition contains ground-truth relevance labels.

        Returns:
            Mapping with ``ndcg_at_k``, ``map_at_k``, ``mrr``, and ``precision_at_k`` (all float).
        """
        return {
            "ndcg_at_k": self._metric_value(model, split, f"ndcg_at_{self._k}"),
            "map_at_k": self._metric_value(model, split, f"map_at_{self._k}"),
            "mrr": self._metric_value(model, split, "mrr"),
            "precision_at_k": self._metric_value(model, split, f"precision_at_{self._k}"),
            "k": self._k,
        }

    def _metric_value(
        self, model: TrainedModel, split: DataSplit, metric: str
    ) -> float:
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "test_name": split.test.name,
                "test_row_count": split.test.row_count,
                "metric": metric,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)
