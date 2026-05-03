"""``ImageClassificationPipeline`` — image loading → augmentation →
CNN/ViT training → evaluation.
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


class ImageClassificationPipeline(SubTapestry):
    """Image loading, augmentation, CNN/ViT training, and evaluation."""

    _image_metrics: tuple[str, ...] = (
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
        label_column: str,
        architecture: str = "cnn",
        augment: bool = True,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "ImageClassificationPipeline: pool must be a DatabaseConnectionPool"
            )
        if not isinstance(query, str) or not query:
            raise ValueError(
                "ImageClassificationPipeline: query must be a non-empty string"
            )
        if not isinstance(image_column, str) or not image_column:
            raise ValueError(
                "ImageClassificationPipeline: image_column must be a non-empty string"
            )
        if not isinstance(label_column, str) or not label_column:
            raise ValueError(
                "ImageClassificationPipeline: label_column must be a non-empty string"
            )
        allowed = {"cnn", "vit"}
        if architecture not in allowed:
            raise ValueError(
                f"ImageClassificationPipeline: architecture must be one of {allowed}"
            )
        self._pool = pool
        self._query = query
        self._image_column = image_column
        self._label_column = label_column
        self._architecture = architecture
        self._augment = augment
        super().__init__(_config=_config, **kwargs)

    @property
    def architecture(self) -> str:
        return self._architecture

    async def process(self, **_: Any) -> EvalReport:
        """Load images, optionally augment, train the configured architecture, and return the EvalReport.

        Returns:
            EvalReport containing accuracy, precision, recall, and f1 metrics.
        """
        with Tapestry() as inner:
            dataset = DatasetLoader(
                name="image-classification",
                feature_names=(self._image_column,),
                target_name=self._label_column,
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
                algorithm=self._architecture,
                hyperparameters={"augment": self._augment},
                _config=KnotConfig(id="train"),
            )
            Evaluator(
                model=trained,
                split=split,
                metrics=self._image_metrics,
                _config=KnotConfig(id="evaluate"),
            )
        inner_result = await self._run_inner(inner)
        return inner_result.outputs["evaluate"]
