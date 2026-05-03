"""``ComputerVisionPipeline`` — end-to-end image classification
SubTapestry.

Composes data load → split → image-embedding extraction → train →
evaluate. The :class:`ImageEmbeddingExtractor` knot fans the configured
:class:`ImageEncoderProvider` over the named image column so the
downstream trainer sees an :class:`MLDataset` whose ``feature_names``
carry the augmented embedding feature.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.ml.data_prep.dataset_loader import DatasetLoader
from pirn.domains.ml.data_prep.train_test_split import TrainTestSplit
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.features.image_embedding_extractor import (
    ImageEmbeddingExtractor,
)
from pirn.domains.ml.image_encoder_provider import ImageEncoderProvider
from pirn.domains.ml.training.trainer import Trainer
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


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
        pool: DatabaseConnectionPool,
        query: str,
        image_column: str,
        target_column: str,
        image_encoder: ImageEncoderProvider,
        algorithm: str = "logistic",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "ComputerVisionPipeline: pool must be a DatabaseConnectionPool"
            )
        if not isinstance(query, str) or not query:
            raise ValueError(
                "ComputerVisionPipeline: query must be a non-empty string"
            )
        if not isinstance(image_column, str) or not image_column:
            raise ValueError(
                "ComputerVisionPipeline: image_column must be a non-empty string"
            )
        if not isinstance(target_column, str) or not target_column:
            raise ValueError(
                "ComputerVisionPipeline: target_column must be a non-empty string"
            )
        if not isinstance(image_encoder, ImageEncoderProvider):
            raise TypeError(
                "ComputerVisionPipeline: image_encoder must be an "
                "ImageEncoderProvider"
            )
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "ComputerVisionPipeline: algorithm must be a non-empty string"
            )
        self._pool = pool
        self._query = query
        self._image_column = image_column
        self._target_column = target_column
        self._image_encoder = image_encoder
        self._algorithm = algorithm
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> EvalReport:
        """Load data, split, extract image embeddings, train a classifier, and return the resulting EvalReport.

        Returns:
            EvalReport containing accuracy, precision, recall, and f1 metrics
            from the image-classification evaluation stage.
        """
        with Tapestry() as inner:
            dataset = DatasetLoader(
                name="computer-vision",
                feature_names=(self._image_column,),
                target_name=self._target_column,
                pool=self._pool,
                query=self._query,
                _config=KnotConfig(id="load"),
            )
            split = TrainTestSplit(
                dataset=dataset,
                _config=KnotConfig(id="split"),
            )
            embedded = ImageEmbeddingExtractor(
                split=split,
                image_column=self._image_column,
                image_encoder=self._image_encoder,
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
