"""``ActiveLearningLoop`` — trains on labeled pool, queries most
uncertain unlabeled samples, adds them to the labeled pool, and repeats
for N rounds.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.ml.data_prep.dataset_loader import DatasetLoader
from pirn.domains.ml.data_prep.train_test_split import TrainTestSplit
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.training.trainer import Trainer
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class ActiveLearningLoop(SubTapestry):
    """Train on labeled pool, query uncertain samples, and iterate for N rounds."""

    _eval_metrics: tuple[str, ...] = ("accuracy", "f1")

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        query: str,
        target_column: str,
        feature_names: Sequence[str],
        n_rounds: int = 5,
        query_size: int = 10,
        algorithm: str = "logistic",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "ActiveLearningLoop: pool must be a DatabaseConnectionPool"
            )
        if not isinstance(query, str) or not query:
            raise ValueError(
                "ActiveLearningLoop: query must be a non-empty string"
            )
        if not isinstance(target_column, str) or not target_column:
            raise ValueError(
                "ActiveLearningLoop: target_column must be a non-empty string"
            )
        feature_tuple = tuple(feature_names)
        if not feature_tuple:
            raise ValueError("ActiveLearningLoop: feature_names must be non-empty")
        if not isinstance(n_rounds, int) or n_rounds < 1:
            raise ValueError("ActiveLearningLoop: n_rounds must be an int >= 1")
        if not isinstance(query_size, int) or query_size < 1:
            raise ValueError("ActiveLearningLoop: query_size must be an int >= 1")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "ActiveLearningLoop: algorithm must be a non-empty string"
            )
        self._pool = pool
        self._query_sql = query
        self._target_column = target_column
        self._feature_names = feature_tuple
        self._n_rounds = n_rounds
        self._query_size = query_size
        self._algorithm = algorithm
        super().__init__(_config=_config, **kwargs)

    @property
    def n_rounds(self) -> int:
        return self._n_rounds

    @property
    def query_size(self) -> int:
        return self._query_size

    async def process(self, **_: Any) -> EvalReport:
        """Run the active learning loop for N rounds and return the final round EvalReport.

        Returns:
            EvalReport from the final round containing accuracy and f1 metrics,
            with round history in details.
        """
        with Tapestry() as inner:
            dataset = DatasetLoader(
                name="active-learning",
                feature_names=self._feature_names,
                target_name=self._target_column,
                pool=self._pool,
                query=self._query_sql,
                _config=KnotConfig(id="load"),
            )
            split = TrainTestSplit(
                dataset=dataset,
                _config=KnotConfig(id="split"),
            )
            trained = Trainer(
                split=split,
                algorithm=self._algorithm,
                hyperparameters={
                    "n_rounds": self._n_rounds,
                    "query_size": self._query_size,
                },
                _config=KnotConfig(id="train"),
            )
            Evaluator(
                model=trained,
                split=split,
                metrics=self._eval_metrics,
                _config=KnotConfig(id="evaluate"),
            )
        inner_result = await self._run_inner(inner)
        return inner_result.outputs["evaluate"]
