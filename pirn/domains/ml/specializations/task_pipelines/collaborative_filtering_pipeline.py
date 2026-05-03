"""``CollaborativeFilteringPipeline`` — matrix factorisation (ALS/SVD)
on user-item interactions, returning trained model and top-K recommendations.
"""

from __future__ import annotations

from typing import Any, Sequence

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
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class CollaborativeFilteringPipeline(SubTapestry):
    """Matrix factorisation on user-item interactions with ranking evaluation."""

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        query: str,
        user_column: str,
        item_column: str,
        rating_column: str,
        algorithm: str = "als",
        top_k: int = 10,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "CollaborativeFilteringPipeline: pool must be a DatabaseConnectionPool"
            )
        if not isinstance(query, str) or not query:
            raise ValueError(
                "CollaborativeFilteringPipeline: query must be a non-empty string"
            )
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
        allowed = {"als", "svd"}
        if algorithm not in allowed:
            raise ValueError(
                f"CollaborativeFilteringPipeline: algorithm must be one of {allowed}"
            )
        if not isinstance(top_k, int) or top_k < 1:
            raise ValueError(
                "CollaborativeFilteringPipeline: top_k must be an int >= 1"
            )
        self._pool = pool
        self._query = query
        self._user_column = user_column
        self._item_column = item_column
        self._rating_column = rating_column
        self._algorithm = algorithm
        self._top_k = top_k
        super().__init__(_config=_config, **kwargs)

    @property
    def top_k(self) -> int:
        return self._top_k

    async def process(self, **_: Any) -> EvalReport:
        """Train a matrix factorisation model and evaluate with ranking metrics.

        Returns:
            EvalReport containing ndcg_at_k, mrr, and map_at_k ranking metrics.
        """
        feature_names = (self._user_column, self._item_column)
        with Tapestry() as inner:
            dataset = DatasetLoader(
                name="collaborative-filtering",
                feature_names=feature_names,
                target_name=self._rating_column,
                pool=self._pool,
                query=self._query,
                _config=KnotConfig(id="load"),
            )
            split = TrainTestSplit(
                dataset=dataset,
                _config=KnotConfig(id="split"),
            )
            trained = Trainer(
                split=split,
                algorithm=self._algorithm,
                hyperparameters={"top_k": self._top_k},
                _config=KnotConfig(id="train"),
            )
            RankingEvalPipeline(
                model=trained,
                split=split,
                k=self._top_k,
                _config=KnotConfig(id="evaluate"),
            )
        inner_result = await self._run_inner(inner)
        return inner_result.outputs["evaluate"]
