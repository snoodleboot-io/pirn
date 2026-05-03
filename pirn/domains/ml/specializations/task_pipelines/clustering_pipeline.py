"""``ClusteringPipeline`` — feature scaling → KMeans/DBSCAN/GMM →
cluster assignment → silhouette score evaluation.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.ml.data_prep.dataset_loader import DatasetLoader
from pirn.domains.ml.data_prep.train_test_split import TrainTestSplit
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.features.scaler import Scaler
from pirn.domains.ml.training.trainer import Trainer
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class ClusteringPipeline(SubTapestry):
    """Scale features, fit a clustering model, and evaluate with silhouette score."""

    _clustering_metrics: tuple[str, ...] = ("silhouette", "davies_bouldin", "inertia")

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        query: str,
        feature_names: Sequence[str],
        algorithm: str = "kmeans",
        n_clusters: int = 8,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "ClusteringPipeline: pool must be a DatabaseConnectionPool"
            )
        if not isinstance(query, str) or not query:
            raise ValueError(
                "ClusteringPipeline: query must be a non-empty string"
            )
        feature_tuple = tuple(feature_names)
        if not feature_tuple:
            raise ValueError("ClusteringPipeline: feature_names must be non-empty")
        allowed = {"kmeans", "dbscan", "gmm"}
        if algorithm not in allowed:
            raise ValueError(
                f"ClusteringPipeline: algorithm must be one of {allowed}"
            )
        if not isinstance(n_clusters, int) or n_clusters < 2:
            raise ValueError("ClusteringPipeline: n_clusters must be an int >= 2")
        self._pool = pool
        self._query = query
        self._feature_names = feature_tuple
        self._algorithm = algorithm
        self._n_clusters = n_clusters
        super().__init__(_config=_config, **kwargs)

    @property
    def n_clusters(self) -> int:
        return self._n_clusters

    async def process(self, **_: Any) -> EvalReport:
        """Scale features, fit a clustering model, and return an EvalReport with silhouette and Davies-Bouldin scores.

        Returns:
            EvalReport containing silhouette, davies_bouldin, and inertia metrics.
        """
        with Tapestry() as inner:
            dataset = DatasetLoader(
                name="clustering",
                feature_names=self._feature_names,
                target_name=None,
                pool=self._pool,
                query=self._query,
                _config=KnotConfig(id="load"),
            )
            split = TrainTestSplit(
                dataset=dataset,
                _config=KnotConfig(id="split"),
            )
            preprocessed = Scaler(
                split=split,
                columns=self._feature_names,
                method="standardise",
                _config=KnotConfig(id="preprocess"),
            )
            trained = Trainer(
                split=preprocessed,
                algorithm=self._algorithm,
                hyperparameters={"n_clusters": self._n_clusters},
                _config=KnotConfig(id="train"),
            )
            Evaluator(
                model=trained,
                split=preprocessed,
                metrics=self._clustering_metrics,
                _config=KnotConfig(id="evaluate"),
            )
        inner_result = await self._run_inner(inner)
        return inner_result.outputs["evaluate"]
