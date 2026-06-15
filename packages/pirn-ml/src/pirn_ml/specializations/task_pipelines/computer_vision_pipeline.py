"""``ComputerVisionPipeline`` — end-to-end image classification
SubTapestry.

Composes data load → split → image-embedding extraction → train →
evaluate. The :class:`ImageEmbeddingExtractor` knot fans the configured
:class:`ImageEncoderProvider` over the named image column so the
downstream trainer sees an :class:`DatasetManifest` whose ``feature_names``
carry the augmented embedding feature.

Algorithm:
    1. Receive ``pool``, ``query``, ``image_column``, ``target_column``,
       ``image_encoder``, and ``algorithm`` via process().
    2. Validate all inputs.
    3. Wire DatasetLoader → TrainTestSplit → ImageEmbeddingExtractor →
       Trainer → Evaluator in an inner Tapestry.
    4. Run via _run_inner() and return the EvalMetadata.

Math:
    Image embedding: e = f_enc(img; theta_enc)  where e in R^d
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
from pirn_ml.features.image_embedding_extractor import (
    ImageEmbeddingExtractor,
)
from pirn_ml.image_encoder_provider import ImageEncoderProvider
from pirn_ml.training.trainer import Trainer


class ComputerVisionPipeline(SubTapestry):
    """End-to-end image classification SubTapestry."""

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
        image_column: Knot | str,
        target_column: Knot | str,
        image_encoder: Knot | ImageEncoderProvider,
        algorithm: Knot | str = "logistic",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            query=query,
            image_column=image_column,
            target_column=target_column,
            image_encoder=image_encoder,
            algorithm=algorithm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        pool: DatabaseConnectionPool | None = None,
        query: str = "",
        image_column: str = "",
        target_column: str = "",
        image_encoder: ImageEncoderProvider | None = None,
        algorithm: str = "logistic",
        **_: Any,
    ) -> Any:
        """Load data, split, extract image embeddings, train a classifier, and return the resulting EvalMetadata.

        Args:
            pool: DatabaseConnectionPool for loading the dataset.
            query: Non-empty SQL query string.
            image_column: Non-empty name of the image column.
            target_column: Non-empty name of the target column.
            image_encoder: ImageEncoderProvider for embedding extraction.
            algorithm: Non-empty algorithm identifier.

        Returns:
            EvalReportPayload containing accuracy, precision, recall, and f1 metrics
            from the image-classification evaluation stage.

        Raises:
            ValueError: If any input fails validation.
            TypeError: If pool or image_encoder have wrong types.
        """
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError("ComputerVisionPipeline: pool must be a DatabaseConnectionPool")
        if not isinstance(query, str) or not query:
            raise ValueError("ComputerVisionPipeline: query must be a non-empty string")
        if not isinstance(image_column, str) or not image_column:
            raise ValueError("ComputerVisionPipeline: image_column must be a non-empty string")
        if not isinstance(target_column, str) or not target_column:
            raise ValueError("ComputerVisionPipeline: target_column must be a non-empty string")
        if not isinstance(image_encoder, ImageEncoderProvider):
            raise TypeError("ComputerVisionPipeline: image_encoder must be an ImageEncoderProvider")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("ComputerVisionPipeline: algorithm must be a non-empty string")
        dataset = DatasetLoader(
            name="computer-vision",
            feature_names=(image_column,),
            target_name=target_column,
            pool=pool,
            query=query,
            _config=KnotConfig(id="load"),
        )
        split = TrainTestSplit(
            dataset=dataset,
            _config=KnotConfig(id="split"),
        )
        embedded = ImageEmbeddingExtractor(
            split=split,
            image_column=image_column,
            image_encoder=image_encoder,
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
