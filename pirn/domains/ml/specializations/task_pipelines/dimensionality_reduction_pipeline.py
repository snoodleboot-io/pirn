"""``DimensionalityReductionPipeline`` — PCA/UMAP/t-SNE → reduced
embeddings → optional downstream task evaluation.

Algorithm:
    1. Receive ``pool``, ``query``, ``feature_names``, ``algorithm``,
       and ``n_components`` via process().
    2. Validate all inputs.
    3. Wire DatasetLoader → TrainTestSplit → Scaler → Trainer → Evaluator
       in an inner Tapestry.
    4. Run via _run_inner() and return the EvalMetadata.

Math:
    PCA: find W = [w_1, ..., w_k] that maximises variance:
        w_i = argmax_{||w||=1} w^T Sigma w  subject to w perp w_1..w_{i-1}
        Sigma = (1/n) X^T X  (sample covariance)

    Explained variance ratio for component i: lambda_i / sum_j lambda_j

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
from pirn.nodes.sub_tapestry import SubTapestry


class DimensionalityReductionPipeline(SubTapestry):
    """Scale, reduce dimensionality, and evaluate reconstruction quality."""

    _reduction_metrics: tuple[str, ...] = (
        "explained_variance",
        "reconstruction_error",
        "trustworthiness",
    )
    valid_algorithms: ClassVar[frozenset[str]] = frozenset({"pca", "umap", "tsne"})

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        query: Knot | str,
        feature_names: Knot | Sequence[str],
        algorithm: Knot | str = "pca",
        n_components: Knot | int = 2,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            query=query,
            feature_names=feature_names,
            algorithm=algorithm,
            n_components=n_components,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        pool: DatabaseConnectionPool | None = None,
        query: str = "",
        feature_names: Sequence[str] = (),
        algorithm: str = "pca",
        n_components: int = 2,
        **_: Any,
    ) -> Any:
        """Scale, reduce dimensionality, and return an EvalMetadata with reconstruction quality metrics.

        Args:
            pool: DatabaseConnectionPool for loading the dataset.
            query: Non-empty SQL query string.
            feature_names: Non-empty sequence of feature column names.
            algorithm: Dimensionality reduction algorithm; must be one of {"pca", "umap", "tsne"}.
            n_components: Number of output dimensions; must be int >= 1.

        Returns:
            EvalReportPayload containing explained_variance, reconstruction_error, and trustworthiness metrics.

        Raises:
            ValueError: If any input fails validation.
            TypeError: If pool is not a DatabaseConnectionPool.
        """
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "DimensionalityReductionPipeline: pool must be a DatabaseConnectionPool"
            )
        if not isinstance(query, str) or not query:
            raise ValueError("DimensionalityReductionPipeline: query must be a non-empty string")
        feature_tuple = tuple(feature_names)
        if not feature_tuple:
            raise ValueError("DimensionalityReductionPipeline: feature_names must be non-empty")
        if algorithm not in self.valid_algorithms:
            raise ValueError(
                f"DimensionalityReductionPipeline: algorithm must be one of {sorted(self.valid_algorithms)}"
            )
        if not isinstance(n_components, int) or n_components < 1:
            raise ValueError("DimensionalityReductionPipeline: n_components must be an int >= 1")
        dataset = DatasetLoader(
            name="dim-reduction",
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
            hyperparameters={"n_components": n_components},
            _config=KnotConfig(id="train"),
        )
        return Evaluator(
            model=trained,
            split=preprocessed,
            metrics=self._reduction_metrics,
            _config=KnotConfig(id="evaluate"),
        )
