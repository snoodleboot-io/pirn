"""``NamedEntityRecognitionPipeline`` — tokenise → NER model inference →
entity extraction, returning a list of (entity, label, span) tuples.
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


class NamedEntityRecognitionPipeline(SubTapestry):
    """Tokenise text, run NER inference, and evaluate entity extraction."""

    _ner_metrics: tuple[str, ...] = ("precision", "recall", "f1")

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        query: str,
        text_column: str,
        label_column: str,
        algorithm: str = "crf",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "NamedEntityRecognitionPipeline: pool must be a DatabaseConnectionPool"
            )
        if not isinstance(query, str) or not query:
            raise ValueError(
                "NamedEntityRecognitionPipeline: query must be a non-empty string"
            )
        if not isinstance(text_column, str) or not text_column:
            raise ValueError(
                "NamedEntityRecognitionPipeline: text_column must be a non-empty string"
            )
        if not isinstance(label_column, str) or not label_column:
            raise ValueError(
                "NamedEntityRecognitionPipeline: label_column must be a non-empty string"
            )
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "NamedEntityRecognitionPipeline: algorithm must be a non-empty string"
            )
        self._pool = pool
        self._query = query
        self._text_column = text_column
        self._label_column = label_column
        self._algorithm = algorithm
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> EvalReport:
        """Tokenise, train NER model, and return an EvalReport with entity-level precision/recall/F1.

        Returns:
            EvalReport containing precision, recall, and f1 metrics from the NER evaluation stage.
        """
        with Tapestry() as inner:
            dataset = DatasetLoader(
                name="ner",
                feature_names=(self._text_column,),
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
                algorithm=self._algorithm,
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
