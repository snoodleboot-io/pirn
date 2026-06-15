"""``AnomalyDetectionPipeline`` — end-to-end anomaly detection pipeline:
fits Isolation Forest, LOF, or autoencoder on normal data, scores the
test set, and returns anomaly flags and scores.

Algorithm:
    1. Receive ``pool``, ``query``, ``feature_names``, ``algorithm``,
       and ``contamination`` via process().
    2. Validate all inputs.
    3. Wire DatasetLoader → TrainTestSplit → Scaler → Trainer → Evaluator
       in an inner Tapestry.
    4. Run via _run_inner() and return the EvalMetadata.

Math:
    Isolation Forest anomaly score:
        s(x, n) = 2^(-E[h(x)] / c(n))
        where h(x) = path length to isolate x, c(n) = 2*H(n-1) - 2*(n-1)/n.

    Anomaly threshold at contamination fraction p:
        threshold = percentile(scores, 100*(1-p))

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

from pirn.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_ml.data_prep.dataset_loader import DatasetLoader
from pirn_ml.data_prep.train_test_split import TrainTestSplit
from pirn_ml.evaluation.evaluator import Evaluator
from pirn_ml.features.scaler import Scaler
from pirn_ml.training.trainer import Trainer


class AnomalyDetectionPipeline(SubTapestry):
    """Fit an anomaly detector on normal data and score the test set."""

    _anomaly_metrics: tuple[str, ...] = ("precision", "recall", "f1", "roc_auc")
    valid_algorithms: ClassVar[frozenset[str]] = frozenset(
        {"isolation_forest", "lof", "autoencoder"}
    )

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        query: Knot | str,
        feature_names: Knot | Sequence[str],
        algorithm: Knot | str = "isolation_forest",
        contamination: Knot | float = 0.1,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            query=query,
            feature_names=feature_names,
            algorithm=algorithm,
            contamination=contamination,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        pool: DatabaseConnectionPool | None = None,
        query: str = "",
        feature_names: Sequence[str] = (),
        algorithm: str = "isolation_forest",
        contamination: float = 0.1,
        **_: Any,
    ) -> Any:
        """Load data, scale, train anomaly detector, and return an EvalMetadata with anomaly metrics.

        Args:
            pool: DatabaseConnectionPool for loading the dataset.
            query: Non-empty SQL query string.
            feature_names: Non-empty sequence of feature column names.
            algorithm: Anomaly detection algorithm; must be one of {"isolation_forest", "lof", "autoencoder"}.
            contamination: Expected fraction of anomalies; must be in (0, 0.5).

        Returns:
            EvalReportPayload containing precision, recall, f1, and roc_auc metrics from the evaluation stage.

        Raises:
            ValueError: If any input fails validation.
            TypeError: If pool is not a DatabaseConnectionPool.
        """
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError("AnomalyDetectionPipeline: pool must be a DatabaseConnectionPool")
        if not isinstance(query, str) or not query:
            raise ValueError("AnomalyDetectionPipeline: query must be a non-empty string")
        feature_tuple = tuple(feature_names)
        if not feature_tuple:
            raise ValueError("AnomalyDetectionPipeline: feature_names must be non-empty")
        if algorithm not in self.valid_algorithms:
            raise ValueError(
                f"AnomalyDetectionPipeline: algorithm must be one of {sorted(self.valid_algorithms)}"
            )
        if not isinstance(contamination, (int, float)) or not 0.0 < contamination < 0.5:
            raise ValueError("AnomalyDetectionPipeline: contamination must be in (0, 0.5)")
        contamination_f = float(contamination)
        dataset = DatasetLoader(
            name="anomaly-detection",
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
            hyperparameters={"contamination": contamination_f},
            _config=KnotConfig(id="train"),
        )
        return Evaluator(
            model=trained,
            split=preprocessed,
            metrics=self._anomaly_metrics,
            _config=KnotConfig(id="evaluate"),
        )
