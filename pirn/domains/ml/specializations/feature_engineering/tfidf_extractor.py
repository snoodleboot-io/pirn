"""``TFIDFExtractor`` — compute TF-IDF features for a text column.

Appends ``tfidf_<i>`` feature names for each of the ``max_features``
TF-IDF dimensions. The feature-name catalogue is updated at the
orchestration layer; concrete subclasses materialise the sparse matrix.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset


class TFIDFExtractor(Knot):
    """Append TF-IDF feature names for a text column."""

    def __init__(
        self,
        *,
        split: Knot,
        text_column: str,
        max_features: int = 100,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(split, Knot):
            raise TypeError("TFIDFExtractor: split must be a Knot")
        if not isinstance(text_column, str) or not text_column:
            raise ValueError(
                "TFIDFExtractor: text_column must be a non-empty string"
            )
        if not isinstance(max_features, int):
            raise TypeError("TFIDFExtractor: max_features must be an int")
        if max_features < 1:
            raise ValueError("TFIDFExtractor: max_features must be >= 1")
        self._text_column = text_column
        self._max_features = max_features
        super().__init__(split=split, _config=_config, **kwargs)

    @property
    def max_features(self) -> int:
        return self._max_features

    async def process(self, split: DataSplit, **_: Any) -> DataSplit:
        """Append tfidf feature names for the text column to every partition.

        Args:
            split: DataSplit whose partitions receive the TF-IDF feature names.

        Returns:
            DataSplit with ``tfidf_<i>`` feature names appended to every partition,
            and the original text column removed from the feature list.
        """
        now = datetime.now(timezone.utc)
        return DataSplit(
            train=self._add_tfidf_features(split.train, now),
            test=self._add_tfidf_features(split.test, now),
            validation=(
                self._add_tfidf_features(split.validation, now)
                if split.validation is not None
                else None
            ),
        )

    def _add_tfidf_features(
        self, dataset: MLDataset, fetched_at: datetime
    ) -> MLDataset:
        existing = [
            f for f in dataset.feature_names if f != self._text_column
        ]
        tfidf_features = [f"tfidf_{i}" for i in range(self._max_features)]
        return MLDataset(
            name=f"{dataset.name}:tfidf",
            feature_names=tuple(existing + tfidf_features),
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=fetched_at,
        )
