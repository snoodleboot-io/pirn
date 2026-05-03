"""``TextClassificationPipeline`` — TF-IDF/embedding → classifier train
→ evaluation, supporting binary and multiclass text classification.
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
from pirn.domains.ml.training.trainer import Trainer
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class TextClassificationPipeline(SubTapestry):
    """TF-IDF or embedding features → classifier train → evaluation."""

    _classification_metrics: tuple[str, ...] = (
        "accuracy",
        "precision",
        "recall",
        "f1",
    )

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        query: str,
        text_column: str,
        target_column: str,
        vectorizer: str = "tfidf",
        algorithm: str = "logistic",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "TextClassificationPipeline: pool must be a DatabaseConnectionPool"
            )
        if not isinstance(query, str) or not query:
            raise ValueError(
                "TextClassificationPipeline: query must be a non-empty string"
            )
        if not isinstance(text_column, str) or not text_column:
            raise ValueError(
                "TextClassificationPipeline: text_column must be a non-empty string"
            )
        if not isinstance(target_column, str) or not target_column:
            raise ValueError(
                "TextClassificationPipeline: target_column must be a non-empty string"
            )
        allowed_vec = {"tfidf", "embedding"}
        if vectorizer not in allowed_vec:
            raise ValueError(
                f"TextClassificationPipeline: vectorizer must be one of {allowed_vec}"
            )
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "TextClassificationPipeline: algorithm must be a non-empty string"
            )
        self._pool = pool
        self._query = query
        self._text_column = text_column
        self._target_column = target_column
        self._vectorizer = vectorizer
        self._algorithm = algorithm
        super().__init__(_config=_config, **kwargs)

    @property
    def vectorizer(self) -> str:
        return self._vectorizer

    async def process(self, **_: Any) -> EvalReport:
        """Load text data, vectorize, train a classifier, and return the classification EvalReport.

        Returns:
            EvalReport containing accuracy, precision, recall, and f1 metrics.
        """
        with Tapestry() as inner:
            dataset = DatasetLoader(
                name="text-classification",
                feature_names=(self._text_column,),
                target_name=self._target_column,
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
                hyperparameters={"vectorizer": self._vectorizer},
                _config=KnotConfig(id="train"),
            )
            Evaluator(
                model=trained,
                split=split,
                metrics=self._classification_metrics,
                _config=KnotConfig(id="evaluate"),
            )
        inner_result = await self._run_inner(inner)
        return inner_result.outputs["evaluate"]
