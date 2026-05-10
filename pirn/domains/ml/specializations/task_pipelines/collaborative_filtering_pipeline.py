"""``CollaborativeFilteringPipeline`` — matrix factorisation (ALS/SVD)
on user-item interactions, returning trained model and top-K recommendations.

Algorithm:
    1. Receive ``pool``, ``query``, ``user_column``, ``item_column``,
       ``rating_column``, ``algorithm``, and ``top_k`` via process().
    2. Validate all inputs.
    3. Wire DatasetLoader → TrainTestSplit → Trainer → RankingEvalPipeline
       in an inner Tapestry.
    4. Run via _run_inner() and return the EvalMetadata.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.ml.data_prep.dataset_loader import DatasetLoader
from pirn.domains.ml.data_prep.train_test_split import TrainTestSplit
from pirn.domains.ml.specializations.evaluation.ranking_eval_pipeline import (
    RankingEvalPipeline,
)
from pirn.domains.ml.training.trainer import Trainer
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class CollaborativeFilteringPipeline(SubTapestry):
    """Matrix factorisation on user-item interactions with ranking evaluation."""

    valid_algorithms: ClassVar[frozenset[str]] = frozenset({"als", "svd"})

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        query: Knot | str,
        user_column: Knot | str,
        item_column: Knot | str,
        rating_column: Knot | str,
        algorithm: Knot | str = "als",
        top_k: Knot | int = 10,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            query=query,
            user_column=user_column,
            item_column=item_column,
            rating_column=rating_column,
            algorithm=algorithm,
            top_k=top_k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        pool: DatabaseConnectionPool | None = None,
        query: str = "",
        user_column: str = "",
        item_column: str = "",
        rating_column: str = "",
        algorithm: str = "als",
        top_k: int = 10,
        **_: Any,
    ) -> EvalReportPayload:
        """Train a matrix factorisation model and evaluate with ranking metrics.

        Args:
            pool: DatabaseConnectionPool for loading the dataset.
            query: Non-empty SQL query string.
            user_column: Non-empty name of the user ID column.
            item_column: Non-empty name of the item ID column.
            rating_column: Non-empty name of the rating column.
            algorithm: Matrix factorisation algorithm; must be one of {"als", "svd"}.
            top_k: Number of recommendations per user; must be int >= 1.

        Returns:
            EvalReportPayload containing ndcg_at_k, mrr, and map_at_k ranking metrics.

        Raises:
            ValueError: If any input fails validation.
            TypeError: If pool is not a DatabaseConnectionPool.
        """
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError("CollaborativeFilteringPipeline: pool must be a DatabaseConnectionPool")
        if not isinstance(query, str) or not query:
            raise ValueError("CollaborativeFilteringPipeline: query must be a non-empty string")
        if not isinstance(user_column, str) or not user_column:
            raise ValueError(
                "CollaborativeFilteringPipeline: user_column must be a non-empty string"
            )
        if not isinstance(item_column, str) or not item_column:
            raise ValueError(
                "CollaborativeFilteringPipeline: item_column must be a non-empty string"
            )
        if not isinstance(rating_column, str) or not rating_column:
            raise ValueError(
                "CollaborativeFilteringPipeline: rating_column must be a non-empty string"
            )
        if algorithm not in self.valid_algorithms:
            raise ValueError(
                f"CollaborativeFilteringPipeline: algorithm must be one of {sorted(self.valid_algorithms)}"
            )
        if not isinstance(top_k, int) or top_k < 1:
            raise ValueError("CollaborativeFilteringPipeline: top_k must be an int >= 1")
        feature_names = (user_column, item_column)
        with Tapestry() as inner:
            dataset = DatasetLoader(
                name="collaborative-filtering",
                feature_names=feature_names,
                target_name=rating_column,
                pool=pool,
                query=query,
                _config=KnotConfig(id="load"),
            )
            split = TrainTestSplit(
                dataset=dataset,
                _config=KnotConfig(id="split"),
            )
            trained = Trainer(
                split=split,
                algorithm=algorithm,
                hyperparameters={"top_k": top_k},
                _config=KnotConfig(id="train"),
            )
            RankingEvalPipeline(
                model=trained,
                split=split,
                k=top_k,
                _config=KnotConfig(id="evaluate"),
            )
        inner_result = await self._run_inner(inner)
        return inner_result.outputs["evaluate"]
