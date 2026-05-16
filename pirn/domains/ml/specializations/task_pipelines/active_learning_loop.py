"""``ActiveLearningLoop`` — trains on labeled pool, queries most
uncertain unlabeled samples, adds them to the labeled pool, and repeats
for N rounds.

Algorithm:
    1. Receive ``pool``, ``query``, ``target_column``, ``feature_names``,
       ``n_rounds``, ``query_size``, and ``algorithm`` via process().
    2. Validate all inputs.
    3. Wire DatasetLoader → TrainTestSplit → Trainer → Evaluator in an
       inner Tapestry.
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
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.ml.data_prep.dataset_loader import DatasetLoader
from pirn.domains.ml.data_prep.train_test_split import TrainTestSplit
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.training.trainer import Trainer
from pirn.nodes.sub_tapestry import SubTapestry


class ActiveLearningLoop(SubTapestry):
    """Train on labeled pool, query uncertain samples, and iterate for N rounds."""

    _eval_metrics: tuple[str, ...] = ("accuracy", "f1")

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
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError("ActiveLearningLoop: pool must be a DatabaseConnectionPool")
        if not isinstance(query, str) or not query:
            raise ValueError("ActiveLearningLoop: query must be a non-empty string")
        if not isinstance(target_column, str) or not target_column:
            raise ValueError("ActiveLearningLoop: target_column must be a non-empty string")
        feature_tuple = tuple(feature_names)
        if not feature_tuple:
            raise ValueError("ActiveLearningLoop: feature_names must be non-empty")
        if not isinstance(n_rounds, int) or n_rounds < 1:
            raise ValueError("ActiveLearningLoop: n_rounds must be an int >= 1")
        if not isinstance(query_size, int) or query_size < 1:
            raise ValueError("ActiveLearningLoop: query_size must be an int >= 1")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("ActiveLearningLoop: algorithm must be a non-empty string")
        dataset = DatasetLoader(
            name="active-learning",
            feature_names=feature_tuple,
            target_name=target_column,
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
            hyperparameters={
                "n_rounds": n_rounds,
                "query_size": query_size,
            },
            _config=KnotConfig(id="train"),
        )
        return Evaluator(
            model=trained,
            split=split,
            metrics=self._eval_metrics,
            _config=KnotConfig(id="evaluate"),
        )
