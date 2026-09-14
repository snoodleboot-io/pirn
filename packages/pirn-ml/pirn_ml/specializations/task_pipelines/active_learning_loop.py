"""``ActiveLearningLoop`` — trains on labeled pool, queries most
uncertain unlabeled samples, adds them to the labeled pool, and repeats
for N rounds.

Algorithm:
    1. Receive ``pool``, ``query``, ``target_column``, ``feature_names``,
       ``n_rounds``, ``query_size``, and ``algorithm`` via process().
    2. Validate all inputs.
    3. Wire DatasetLoader → TrainTestSplit → Trainer → Evaluator in an
       inner Tapestry (shared graph-building lives in
       :class:`~pirn_ml.specializations.task_pipelines.supervised_task_pipeline.SupervisedTaskPipeline`,
       with no ``Scaler`` stage for this pipeline).
    4. Run via _run_inner() and return the final EvalMetadata.

Math:
    Query strategy (least confidence):
        x* = argmin_{x in U} max_c p(y=c | x; theta)

    Pool growth per round: |L_r| = |L_{r-1}| + query_size
    Total labeled after N rounds: |L_N| = |L_0| + N * query_size

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

from pirn_ml.specializations.task_pipelines.supervised_task_pipeline import (
    SupervisedTaskPipeline,
)


class ActiveLearningLoop(SupervisedTaskPipeline):
    """Train on labeled pool, query uncertain samples, and iterate for N rounds."""

    _dataset_name: ClassVar[str] = "active-learning"
    _metrics: ClassVar[tuple[str, ...]] = ("accuracy", "f1")
    _use_scaler: ClassVar[bool] = False

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        query: Knot | str,
        target_column: Knot | str,
        feature_names: Knot | Sequence[str],
        n_rounds: Knot | int = 5,
        query_size: Knot | int = 10,
        algorithm: Knot | str = "logistic",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            query=query,
            target_column=target_column,
            feature_names=feature_names,
            n_rounds=n_rounds,
            query_size=query_size,
            algorithm=algorithm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        pool: DatabaseConnectionPool | None = None,
        query: str = "",
        target_column: str = "",
        feature_names: Sequence[str] = (),
        n_rounds: int = 5,
        query_size: int = 10,
        algorithm: str = "logistic",
        **_: Any,
    ) -> Any:
        """Run the active learning loop for N rounds and return the final round EvalMetadata.

        Args:
            pool: DatabaseConnectionPool for loading the dataset.
            query: Non-empty SQL query string.
            target_column: Non-empty name of the target column.
            feature_names: Non-empty sequence of feature column names.
            n_rounds: Number of active learning rounds; must be int >= 1.
            query_size: Number of uncertain samples to query per round; must be int >= 1.
            algorithm: Non-empty algorithm identifier.

        Returns:
            EvalReportPayload from the final round containing accuracy and f1 metrics,
            with round history in details.

        Raises:
            ValueError: If any input fails validation.
            TypeError: If pool is not a DatabaseConnectionPool.
        """
        pool = self._require_pool("ActiveLearningLoop", pool)
        query = self._require_query("ActiveLearningLoop", query)
        target_column = self._require_target_column("ActiveLearningLoop", target_column)
        feature_tuple = self._require_feature_names("ActiveLearningLoop", feature_names)
        if not isinstance(n_rounds, int) or n_rounds < 1:
            raise ValueError("ActiveLearningLoop: n_rounds must be an int >= 1")
        if not isinstance(query_size, int) or query_size < 1:
            raise ValueError("ActiveLearningLoop: query_size must be an int >= 1")
        algorithm = self._require_algorithm("ActiveLearningLoop", algorithm)
        return self._build_evaluator(
            pool=pool,
            query=query,
            feature_tuple=feature_tuple,
            target_name=target_column,
            algorithm=algorithm,
            hyperparameters={
                "n_rounds": n_rounds,
                "query_size": query_size,
            },
        )
