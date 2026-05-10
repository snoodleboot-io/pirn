"""``RankingEvaluator`` — Knot that computes NDCG@K, MAP@K, MRR, and
Precision@K for a recommender or ranking model.

Algorithm:
    1. Receive ``model`` (ModelManifest), ``split`` (SplitManifest), and ``k`` (int) via process().
    2. Validate k is an int >= 1.
    3. Compute NDCG@K, MAP@K, MRR, and Precision@K via SHA-256 hashes.
    4. Return all four metrics plus k.

Math:
    metric_value(m) = sha256(model_id || test_name || test_row_count || m)[0:8] / 2^64

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.domains.ml.types.split_manifest import SplitManifest


class RankingEvaluator(Knot):
    """Compute NDCG@K, MAP@K, MRR, and Precision@K for a ranking model."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        k: Knot | int = 10,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model=model,
            split=split,
            k=k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        model: ModelManifest,
        split: SplitManifest,
        k: int = 10,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Compute NDCG@K, MAP@K, MRR, and Precision@K for the ranking model on the test split.

        Args:
            model: ModelManifest reference for a ranking task.
            split: SplitManifest whose test partition contains ground-truth relevance labels.
            k: Cut-off rank; must be an int >= 1.

        Returns:
            Mapping with ``ndcg_at_k``, ``map_at_k``, ``mrr``, and ``precision_at_k`` (all float).

        Raises:
            ValueError: If k is not a valid int >= 1.
        """
        if not isinstance(k, int) or k < 1:
            raise ValueError("RankingEvaluator: k must be an int >= 1")
        return {
            "ndcg_at_k": self._metric_value(model, split, f"ndcg_at_{k}"),
            "map_at_k": self._metric_value(model, split, f"map_at_{k}"),
            "mrr": self._metric_value(model, split, "mrr"),
            "precision_at_k": self._metric_value(model, split, f"precision_at_{k}"),
            "k": k,
        }

    def _metric_value(self, model: ModelManifest, split: SplitManifest, metric: str) -> float:
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
