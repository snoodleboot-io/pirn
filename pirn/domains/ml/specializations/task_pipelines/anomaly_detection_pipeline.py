"""``AnomalyDetectionPipeline`` — end-to-end anomaly detection pipeline:
fits Isolation Forest, LOF, or autoencoder on normal data, scores the
test set, and returns anomaly flags and scores.
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


class AnomalyDetectionPipeline(SubTapestry):
    """Fit an anomaly detector on normal data and score the test set."""

    _anomaly_metrics: tuple[str, ...] = (
        "precision",
        "recall",
        "f1",
        "roc_auc",
    )

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        query: str,
        feature_names: Sequence[str],
        algorithm: str = "isolation_forest",
        contamination: float = 0.1,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "AnomalyDetectionPipeline: pool must be a DatabaseConnectionPool"
            )
        if not isinstance(query, str) or not query:
            raise ValueError(
                "AnomalyDetectionPipeline: query must be a non-empty string"
            )
        feature_tuple = tuple(feature_names)
        if not feature_tuple:
            raise ValueError(
                "AnomalyDetectionPipeline: feature_names must be non-empty"
            )
        allowed = {"isolation_forest", "lof", "autoencoder"}
        if algorithm not in allowed:
            raise ValueError(
                f"AnomalyDetectionPipeline: algorithm must be one of {allowed}"
            )
        if not isinstance(contamination, (int, float)) or not 0.0 < contamination < 0.5:
            raise ValueError(
                "AnomalyDetectionPipeline: contamination must be in (0, 0.5)"
            )
        self._pool = pool
        self._query = query
        self._feature_names = feature_tuple
        self._algorithm = algorithm
        self._contamination = float(contamination)
        super().__init__(_config=_config, **kwargs)

    @property
    def contamination(self) -> float:
        return self._contamination

    async def process(self, **_: Any) -> EvalReport:
        """Load data, scale, train anomaly detector, and return an EvalReport with anomaly metrics.

        Returns:
            EvalReport containing precision, recall, f1, and roc_auc metrics from the evaluation stage.
        """
        with Tapestry() as inner:
            dataset = DatasetLoader(
                name="anomaly-detection",
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
                hyperparameters={"contamination": self._contamination},
                _config=KnotConfig(id="train"),
            )
            Evaluator(
                model=trained,
                split=preprocessed,
                metrics=self._anomaly_metrics,
                _config=KnotConfig(id="evaluate"),
            )
        inner_result = await self._run_inner(inner)
        return inner_result.outputs["evaluate"]
