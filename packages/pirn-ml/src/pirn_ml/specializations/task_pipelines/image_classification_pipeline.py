"""``ImageClassificationPipeline`` — image loading → augmentation →
CNN/ViT training → evaluation.

Algorithm:
    1. Receive ``pool``, ``query``, ``image_column``, ``label_column``,
       ``architecture``, and ``augment`` via process().
    2. Validate all inputs.
    3. Wire DatasetLoader → TrainTestSplit → Trainer → Evaluator in an
       inner Tapestry.
    4. Run via _run_inner() and return the EvalMetadata.

Math:
    CNN cross-entropy loss: L = -(1/n) * sum_i sum_c y_{i,c} * log(p_{i,c})
    Top-1 accuracy = (1/n) * sum_i I(argmax_c p_{i,c} == y_i)
    Top-5 accuracy = (1/n) * sum_i I(y_i in top-5 predictions)

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_ml.data_prep.dataset_loader import DatasetLoader
from pirn_ml.data_prep.train_test_split import TrainTestSplit
from pirn_ml.evaluation.evaluator import Evaluator
from pirn_ml.training.trainer import Trainer


class ImageClassificationPipeline(SubTapestry):
    """Image loading, augmentation, CNN/ViT training, and evaluation."""

    _image_metrics: tuple[str, ...] = ("accuracy", "precision", "recall", "f1")
    valid_architectures: ClassVar[frozenset[str]] = frozenset({"cnn", "vit"})

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        query: Knot | str,
        image_column: Knot | str,
        label_column: Knot | str,
        architecture: Knot | str = "cnn",
        augment: Knot | bool = True,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            query=query,
            image_column=image_column,
            label_column=label_column,
            architecture=architecture,
            augment=augment,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        pool: DatabaseConnectionPool | None = None,
        query: str = "",
        image_column: str = "",
        label_column: str = "",
        architecture: str = "cnn",
        augment: bool = True,
        **_: Any,
    ) -> Any:
        """Load images, optionally augment, train the configured architecture, and return the EvalMetadata.

        Args:
            pool: DatabaseConnectionPool for loading the dataset.
            query: Non-empty SQL query string.
            image_column: Non-empty name of the image column.
            label_column: Non-empty name of the label column.
            architecture: Model architecture; must be one of {"cnn", "vit"}.
            augment: Whether to apply data augmentation.

        Returns:
            EvalReportPayload containing accuracy, precision, recall, and f1 metrics.

        Raises:
            ValueError: If any input fails validation.
            TypeError: If pool is not a DatabaseConnectionPool.
        """
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError("ImageClassificationPipeline: pool must be a DatabaseConnectionPool")
        if not isinstance(query, str) or not query:
            raise ValueError("ImageClassificationPipeline: query must be a non-empty string")
        if not isinstance(image_column, str) or not image_column:
            raise ValueError("ImageClassificationPipeline: image_column must be a non-empty string")
        if not isinstance(label_column, str) or not label_column:
            raise ValueError("ImageClassificationPipeline: label_column must be a non-empty string")
        if architecture not in self.valid_architectures:
            raise ValueError(
                f"ImageClassificationPipeline: architecture must be one of {sorted(self.valid_architectures)}"
            )
        dataset = DatasetLoader(
            name="image-classification",
            feature_names=(image_column,),
            target_name=label_column,
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
            algorithm=architecture,
            hyperparameters={"augment": augment},
            _config=KnotConfig(id="train"),
        )
        return Evaluator(
            model=trained,
            split=split,
            metrics=self._image_metrics,
            _config=KnotConfig(id="evaluate"),
        )
