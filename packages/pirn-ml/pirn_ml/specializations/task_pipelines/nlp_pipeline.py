"""``NLPPipeline`` — end-to-end text classification SubTapestry.

Composes data load → split → embedding extraction → train → evaluate.
The :class:`EmbeddingExtractor` knot fans the configured
:class:`MLEmbeddingProvider` over the named text column so the downstream
trainer sees an :class:`DatasetManifest` whose ``feature_names`` carry the
augmented embedding feature.

Algorithm:
    1. Receive ``pool``, ``query``, ``text_column``, ``target_column``,
       ``embedding_provider``, and ``algorithm`` via process().
    2. Validate all inputs.
    3. Wire DatasetLoader → TrainTestSplit → EmbeddingExtractor → Trainer
       → Evaluator in an inner Tapestry.
    4. Run via _run_inner() and return the EvalMetadata.

Math:
    Text embedding: e = f_enc(text; theta_enc)  where e in R^d
    Classification loss: L = -(1/n) * sum_i sum_c y_{i,c} * log(softmax(W * e_i)_c)

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from typing import Any

from pirn.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_ml.data_prep.dataset_loader import DatasetLoader
from pirn_ml.data_prep.train_test_split import TrainTestSplit
from pirn_ml.evaluation.evaluator import Evaluator
from pirn_ml.features.embedding_extractor import EmbeddingExtractor
from pirn_ml.ml_embedding_provider import MLEmbeddingProvider
from pirn_ml.training.trainer import Trainer


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
        embedding_provider: Knot | MLEmbeddingProvider,
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
        embedding_provider: MLEmbeddingProvider | None = None,
        algorithm: str = "logistic",
        **_: Any,
    ) -> Any:
        """Load data, split, embed the text column, train a text classifier, and return the resulting EvalMetadata.

        Args:
            pool: DatabaseConnectionPool for loading the dataset.
            query: Non-empty SQL query string.
            text_column: Non-empty name of the text column.
            target_column: Non-empty name of the target column.
            embedding_provider: MLEmbeddingProvider for text embedding.
            algorithm: Non-empty algorithm identifier.

        Returns:
            EvalReportPayload containing accuracy, precision, recall, and f1 metrics
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
        if not isinstance(embedding_provider, MLEmbeddingProvider):
            raise TypeError("NLPPipeline: embedding_provider must be an MLEmbeddingProvider")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("NLPPipeline: algorithm must be a non-empty string")
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
        return Evaluator(
            model=trained,
            split=embedded,
            metrics=self._classification_metrics,
            _config=KnotConfig(id="evaluate"),
        )
