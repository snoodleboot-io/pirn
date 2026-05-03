"""``NLPPipeline`` — end-to-end text classification SubTapestry.

Composes data load → split → embedding extraction → train → evaluate.
The :class:`EmbeddingExtractor` knot fans the configured
:class:`EmbeddingProvider` over the named text column so the downstream
trainer sees an :class:`MLDataset` whose ``feature_names`` carry the
augmented embedding feature.
"""

from __future__ import annotations

from typing import Any

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
        pool: DatabaseConnectionPool,
        query: str,
        text_column: str,
        target_column: str,
        embedding_provider: EmbeddingProvider,
        algorithm: str = "logistic",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "NLPPipeline: pool must be a DatabaseConnectionPool"
            )
        if not isinstance(query, str) or not query:
            raise ValueError(
                "NLPPipeline: query must be a non-empty string"
            )
        if not isinstance(text_column, str) or not text_column:
            raise ValueError(
                "NLPPipeline: text_column must be a non-empty string"
            )
        if not isinstance(target_column, str) or not target_column:
            raise ValueError(
                "NLPPipeline: target_column must be a non-empty string"
            )
        if not isinstance(embedding_provider, EmbeddingProvider):
            raise TypeError(
                "NLPPipeline: embedding_provider must be an EmbeddingProvider"
            )
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "NLPPipeline: algorithm must be a non-empty string"
            )
        self._pool = pool
        self._query = query
        self._text_column = text_column
        self._target_column = target_column
        self._embedding_provider = embedding_provider
        self._algorithm = algorithm
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> EvalReport:
        """Load data, split, embed the text column, train a text classifier, and return the resulting EvalReport.

        Returns:
            EvalReport containing accuracy, precision, recall, and f1 metrics
            from the text-classification evaluation stage.
        """
        with Tapestry() as inner:
            dataset = DatasetLoader(
                name="nlp",
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
            embedded = EmbeddingExtractor(
                split=split,
                text_column=self._text_column,
                embedding_provider=self._embedding_provider,
                _config=KnotConfig(id="embed"),
            )
            trained = Trainer(
                split=embedded,
                algorithm=self._algorithm,
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
