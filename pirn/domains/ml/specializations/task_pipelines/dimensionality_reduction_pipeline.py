"""``DimensionalityReductionPipeline`` — PCA/UMAP/t-SNE → reduced
embeddings → optional downstream task evaluation.
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


class DimensionalityReductionPipeline(SubTapestry):
    """Scale, reduce dimensionality, and evaluate reconstruction quality."""

    _reduction_metrics: tuple[str, ...] = (
        "explained_variance",
        "reconstruction_error",
        "trustworthiness",
    )

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        query: str,
        feature_names: Sequence[str],
        algorithm: str = "pca",
        n_components: int = 2,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "DimensionalityReductionPipeline: pool must be a DatabaseConnectionPool"
            )
        if not isinstance(query, str) or not query:
            raise ValueError(
                "DimensionalityReductionPipeline: query must be a non-empty string"
            )
        feature_tuple = tuple(feature_names)
        if not feature_tuple:
            raise ValueError(
                "DimensionalityReductionPipeline: feature_names must be non-empty"
            )
        allowed = {"pca", "umap", "tsne"}
        if algorithm not in allowed:
            raise ValueError(
                f"DimensionalityReductionPipeline: algorithm must be one of {allowed}"
            )
        if not isinstance(n_components, int) or n_components < 1:
            raise ValueError(
                "DimensionalityReductionPipeline: n_components must be an int >= 1"
            )
        self._pool = pool
        self._query = query
        self._feature_names = feature_tuple
        self._algorithm = algorithm
        self._n_components = n_components
        super().__init__(_config=_config, **kwargs)

    @property
    def n_components(self) -> int:
        return self._n_components

    async def process(self, **_: Any) -> EvalReport:
        """Scale, reduce dimensionality, and return an EvalReport with reconstruction quality metrics.

        Returns:
            EvalReport containing explained_variance, reconstruction_error, and trustworthiness metrics.
        """
        with Tapestry() as inner:
            dataset = DatasetLoader(
                name="dim-reduction",
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
                hyperparameters={"n_components": self._n_components},
                _config=KnotConfig(id="train"),
            )
            Evaluator(
                model=trained,
                split=preprocessed,
                metrics=self._reduction_metrics,
                _config=KnotConfig(id="evaluate"),
            )
        inner_result = await self._run_inner(inner)
        return inner_result.outputs["evaluate"]
