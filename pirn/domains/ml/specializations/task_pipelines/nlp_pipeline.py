"""``NLPPipeline`` — end-to-end text classification SubTapestry.

Composes data load → split → embedding extraction → train → evaluate.
The :class:`EmbeddingExtractor` knot fans the configured
:class:`EmbeddingProvider` over the named text column so the downstream
trainer sees an :class:`MLDataset` whose ``feature_names`` carry the
augmented embedding feature.

Algorithm:
    1. Receive ``pool``, ``query``, ``text_column``, ``target_column``,
       ``embedding_provider``, and ``algorithm`` via process().
    2. Validate all inputs.
    3. Wire DatasetLoader → TrainTestSplit → EmbeddingExtractor → Trainer
       → Evaluator in an inner Tapestry.
    4. Run via _run_inner() and return the EvalReport.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.ml.data_prep.dataset_loader import DatasetLoader
from pirn.domains.ml.data_prep.train_test_split import TrainTestSplit
from pirn.domains.ml.embedding_provider import EmbeddingProvider
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.features.embedding_extractor import EmbeddingExtractor
from pirn.domains.ml.training.trainer import Trainer
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class NLPPipeline(SubTapestry):
    """End-to-end NLP text-classification SubTapestry."""

    _classification_metrics: tuple[str, ...] = (
        "accuracy",
        "precision",
        "recall",
        "f1",
    )

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        query: Knot | str,
        text_column: Knot | str,
        target_column: Knot | str,
        embedding_provider: Knot | EmbeddingProvider,
        algorithm: Knot | str = "logistic",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            query=query,
            text_column=text_column,
            target_column=target_column,
            embedding_provider=embedding_provider,
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
        embedding_provider: EmbeddingProvider | None = None,
        algorithm: str = "logistic",
        **_: Any,
    ) -> EvalReport:
        """Load data, split, embed the text column, train a text classifier, and return the resulting EvalReport.

        Args:
            pool: DatabaseConnectionPool for loading the dataset.
            query: Non-empty SQL query string.
            text_column: Non-empty name of the text column.
            target_column: Non-empty name of the target column.
            embedding_provider: EmbeddingProvider for text embedding.
            algorithm: Non-empty algorithm identifier.

        Returns:
            EvalReport containing accuracy, precision, recall, and f1 metrics
            from the text-classification evaluation stage.

        Raises:
            ValueError: If any input fails validation.
            TypeError: If pool or embedding_provider have wrong types.
        """
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError("NLPPipeline: pool must be a DatabaseConnectionPool")
        if not isinstance(query, str) or not query:
            raise ValueError("NLPPipeline: query must be a non-empty string")
        if not isinstance(text_column, str) or not text_column:
            raise ValueError("NLPPipeline: text_column must be a non-empty string")
        if not isinstance(target_column, str) or not target_column:
            raise ValueError("NLPPipeline: target_column must be a non-empty string")
        if not isinstance(embedding_provider, EmbeddingProvider):
            raise TypeError("NLPPipeline: embedding_provider must be an EmbeddingProvider")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("NLPPipeline: algorithm must be a non-empty string")
        with Tapestry() as inner:
            dataset = DatasetLoader(
                name="nlp",
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
            embedded = EmbeddingExtractor(
                split=split,
                text_column=text_column,
                embedding_provider=embedding_provider,
                _config=KnotConfig(id="embed"),
            )
            trained = Trainer(
                split=embedded,
                algorithm=algorithm,
                _config=KnotConfig(id="train"),
            )
            Evaluator(
                model=trained,
                split=embedded,
                metrics=self._classification_metrics,
                _config=KnotConfig(id="evaluate"),
            )
        inner_result = await self._run_inner(inner)
        return inner_result.outputs["evaluate"]
