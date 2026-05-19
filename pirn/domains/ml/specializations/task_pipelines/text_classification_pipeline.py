"""``TextClassificationPipeline`` — TF-IDF/embedding → classifier train
→ evaluation, supporting binary and multiclass text classification.

Algorithm:
    1. Receive ``pool``, ``query``, ``text_column``, ``target_column``,
       ``vectorizer``, and ``algorithm`` via process().
    2. Validate all inputs.
    3. Wire DatasetLoader → TrainTestSplit → Trainer → Evaluator in an
       inner Tapestry.
    4. Run via _run_inner() and return the EvalMetadata.

Math:
    TF-IDF vectorisation: tfidf(t, d) = tf(t, d) * log((1 + N) / (1 + df(t))) + 1
    Classification loss: L = -(1/n) * sum_i sum_c y_{i,c} * log(p_{i,c})

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from typing import Any, ClassVar

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


class TextClassificationPipeline(SubTapestry):
    """TF-IDF or embedding features → classifier train → evaluation."""

    _classification_metrics: tuple[str, ...] = (
        "accuracy",
        "precision",
        "recall",
        "f1",
    )
    valid_vectorizers: ClassVar[frozenset[str]] = frozenset({"tfidf", "embedding"})

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        query: Knot | str,
        text_column: Knot | str,
        target_column: Knot | str,
        vectorizer: Knot | str = "tfidf",
        algorithm: Knot | str = "logistic",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            query=query,
            text_column=text_column,
            target_column=target_column,
            vectorizer=vectorizer,
            algorithm=algorithm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        pool: DatabaseConnectionPool | None = None,
        query: str = "",
        text_column: str = "",
        target_column: str = "",
        vectorizer: str = "tfidf",
        algorithm: str = "logistic",
        **_: Any,
    ) -> Any:
        """Load text data, vectorize, train a classifier, and return the classification EvalMetadata.

        Args:
            pool: DatabaseConnectionPool for loading the dataset.
            query: Non-empty SQL query string.
            text_column: Non-empty name of the text column.
            target_column: Non-empty name of the target column.
            vectorizer: Text vectorization method; must be one of {"tfidf", "embedding"}.
            algorithm: Non-empty algorithm identifier.

        Returns:
            EvalReportPayload containing accuracy, precision, recall, and f1 metrics.

        Raises:
            ValueError: If any input fails validation.
            TypeError: If pool is not a DatabaseConnectionPool.
        """
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError("TextClassificationPipeline: pool must be a DatabaseConnectionPool")
        if not isinstance(query, str) or not query:
            raise ValueError("TextClassificationPipeline: query must be a non-empty string")
        if not isinstance(text_column, str) or not text_column:
            raise ValueError("TextClassificationPipeline: text_column must be a non-empty string")
        if not isinstance(target_column, str) or not target_column:
            raise ValueError("TextClassificationPipeline: target_column must be a non-empty string")
        if vectorizer not in self.valid_vectorizers:
            raise ValueError(
                f"TextClassificationPipeline: vectorizer must be one of {sorted(self.valid_vectorizers)}"
            )
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("TextClassificationPipeline: algorithm must be a non-empty string")
        dataset = DatasetLoader(
            name="text-classification",
            feature_names=(text_column,),
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
            hyperparameters={"vectorizer": vectorizer},
            _config=KnotConfig(id="train"),
        )
        return Evaluator(
            model=trained,
            split=split,
            metrics=self._classification_metrics,
            _config=KnotConfig(id="evaluate"),
        )
