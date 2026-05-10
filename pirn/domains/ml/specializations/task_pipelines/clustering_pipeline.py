"""``ClusteringPipeline`` — feature scaling → KMeans/DBSCAN/GMM →
cluster assignment → silhouette score evaluation.

Algorithm:
    1. Receive ``pool``, ``query``, ``feature_names``, ``algorithm``,
       and ``n_clusters`` via process().
    2. Validate all inputs.
    3. Wire DatasetLoader → TrainTestSplit → Scaler → Trainer → Evaluator
       in an inner Tapestry.
    4. Run via _run_inner() and return the EvalMetadata.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.ml.data_prep.dataset_loader import DatasetLoader
from pirn.domains.ml.data_prep.train_test_split import TrainTestSplit
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.features.scaler import Scaler
from pirn.domains.ml.training.trainer import Trainer
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class ClusteringPipeline(SubTapestry):
    """Scale features, fit a clustering model, and evaluate with silhouette score."""

    _clustering_metrics: tuple[str, ...] = ("silhouette", "davies_bouldin", "inertia")
    valid_algorithms: ClassVar[frozenset[str]] = frozenset({"kmeans", "dbscan", "gmm"})

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        query: Knot | str,
        feature_names: Knot | Sequence[str],
        algorithm: Knot | str = "kmeans",
        n_clusters: Knot | int = 8,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            query=query,
            feature_names=feature_names,
            algorithm=algorithm,
            n_clusters=n_clusters,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        pool: DatabaseConnectionPool | None = None,
        query: str = "",
        feature_names: Sequence[str] = (),
        algorithm: str = "kmeans",
        n_clusters: int = 8,
        **_: Any,
    ) -> EvalReportPayload:
        """Scale features, fit a clustering model, and return an EvalMetadata with silhouette and Davies-Bouldin scores.

        Args:
            pool: DatabaseConnectionPool for loading the dataset.
            query: Non-empty SQL query string.
            feature_names: Non-empty sequence of feature column names.
            algorithm: Clustering algorithm; must be one of {"kmeans", "dbscan", "gmm"}.
            n_clusters: Number of clusters; must be int >= 2.

        Returns:
            EvalReportPayload containing silhouette, davies_bouldin, and inertia metrics.

        Raises:
            ValueError: If any input fails validation.
            TypeError: If pool is not a DatabaseConnectionPool.
        """
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError("ClusteringPipeline: pool must be a DatabaseConnectionPool")
        if not isinstance(query, str) or not query:
            raise ValueError("ClusteringPipeline: query must be a non-empty string")
        feature_tuple = tuple(feature_names)
        if not feature_tuple:
            raise ValueError("ClusteringPipeline: feature_names must be non-empty")
        if algorithm not in self.valid_algorithms:
            raise ValueError(
                f"ClusteringPipeline: algorithm must be one of {sorted(self.valid_algorithms)}"
            )
        if not isinstance(n_clusters, int) or n_clusters < 2:
            raise ValueError("ClusteringPipeline: n_clusters must be an int >= 2")
        with Tapestry() as inner:
            dataset = DatasetLoader(
                name="clustering",
                feature_names=feature_tuple,
                target_name=None,
                pool=pool,
                query=query,
                _config=KnotConfig(id="load"),
            )
            split = TrainTestSplit(
                dataset=dataset,
                _config=KnotConfig(id="split"),
            )
            preprocessed = Scaler(
                split=split,
                columns=feature_tuple,
                method="standardise",
                _config=KnotConfig(id="preprocess"),
            )
            trained = Trainer(
                split=preprocessed,
                algorithm=algorithm,
                hyperparameters={"n_clusters": n_clusters},
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
