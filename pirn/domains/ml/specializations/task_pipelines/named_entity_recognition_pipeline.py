"""``NamedEntityRecognitionPipeline`` — tokenise → NER model inference →
entity extraction, returning a list of (entity, label, span) tuples.

Algorithm:
    1. Receive ``pool``, ``query``, ``text_column``, ``label_column``,
       and ``algorithm`` via process().
    2. Validate all inputs.
    3. Wire DatasetLoader → TrainTestSplit → Trainer → Evaluator in an
       inner Tapestry.
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
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.training.trainer import Trainer
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class NamedEntityRecognitionPipeline(SubTapestry):
    """Tokenise text, run NER inference, and evaluate entity extraction."""

    _ner_metrics: tuple[str, ...] = ("precision", "recall", "f1")

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        query: Knot | str,
        text_column: Knot | str,
        label_column: Knot | str,
        algorithm: Knot | str = "crf",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            query=query,
            text_column=text_column,
            label_column=label_column,
            algorithm=algorithm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        pool: DatabaseConnectionPool = None,
        query: str = "",
        text_column: str = "",
        label_column: str = "",
        algorithm: str = "crf",
        **_: Any,
    ) -> EvalReport:
        """Tokenise, train NER model, and return an EvalReport with entity-level precision/recall/F1.

        Args:
            pool: DatabaseConnectionPool for loading the dataset.
            query: Non-empty SQL query string.
            text_column: Non-empty name of the text column.
            label_column: Non-empty name of the label column.
            algorithm: Non-empty algorithm identifier.

        Returns:
            EvalReport containing precision, recall, and f1 metrics from the NER evaluation stage.

        Raises:
            ValueError: If any input fails validation.
            TypeError: If pool is not a DatabaseConnectionPool.
        """
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError("NamedEntityRecognitionPipeline: pool must be a DatabaseConnectionPool")
        if not isinstance(query, str) or not query:
            raise ValueError("NamedEntityRecognitionPipeline: query must be a non-empty string")
        if not isinstance(text_column, str) or not text_column:
            raise ValueError(
                "NamedEntityRecognitionPipeline: text_column must be a non-empty string"
            )
        if not isinstance(label_column, str) or not label_column:
            raise ValueError(
                "NamedEntityRecognitionPipeline: label_column must be a non-empty string"
            )
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("NamedEntityRecognitionPipeline: algorithm must be a non-empty string")
        with Tapestry() as inner:
            dataset = DatasetLoader(
                name="ner",
                feature_names=(text_column,),
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
                algorithm=algorithm,
                _config=KnotConfig(id="train"),
            )
            Evaluator(
                model=trained,
                split=split,
                metrics=self._ner_metrics,
                _config=KnotConfig(id="evaluate"),
            )
        inner_result = await self._run_inner(inner)
        return inner_result.outputs["evaluate"]
