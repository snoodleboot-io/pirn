"""``TFIDFExtractor`` — compute TF-IDF features for a text column.

Appends ``tfidf_<i>`` feature names for each of the ``max_features``
TF-IDF dimensions. The feature-name catalogue is updated at the
orchestration layer; concrete subclasses materialise the sparse matrix.

Algorithm:
    1. Receive ``split`` (DataSplit), ``text_column``, and ``max_features``
       via process().
    2. Validate all inputs.
    3. Remove the original text column and append tfidf feature names.
    4. Return updated DataSplit.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from datetime import UTC, datetime
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
        text_column: Knot | str,
        max_features: Knot | int = 100,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            text_column=text_column,
            max_features=max_features,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: DataSplit,
        text_column: str = "",
        max_features: int = 100,
        **_: Any,
    ) -> DataSplit:
        """Append tfidf feature names for the text column to every partition.

        Args:
            split: DataSplit whose partitions receive the TF-IDF feature names.
            text_column: Non-empty name of the text column to transform.
            max_features: Number of TF-IDF dimensions; must be an int >= 1.

        Returns:
            DataSplit with ``tfidf_<i>`` feature names appended to every partition,
            and the original text column removed from the feature list.

        Raises:
            ValueError: If text_column is empty or max_features < 1.
            TypeError: If max_features is not an int.
        """
        if not isinstance(text_column, str) or not text_column:
            raise ValueError("TFIDFExtractor: text_column must be a non-empty string")
        if not isinstance(max_features, int):
            raise TypeError("TFIDFExtractor: max_features must be an int")
        if max_features < 1:
            raise ValueError("TFIDFExtractor: max_features must be >= 1")
        now = datetime.now(UTC)
        return DataSplit(
            train=self._add_tfidf_features(split.train, text_column, max_features, now),
            test=self._add_tfidf_features(split.test, text_column, max_features, now),
            validation=(
                self._add_tfidf_features(split.validation, text_column, max_features, now)
                if split.validation is not None
                else None
            ),
        )

    def _add_tfidf_features(
        self,
        dataset: MLDataset,
        text_column: str,
        max_features: int,
        fetched_at: datetime,
    ) -> MLDataset:
        existing = [f for f in dataset.feature_names if f != text_column]
        tfidf_features = [f"tfidf_{i}" for i in range(max_features)]
        return MLDataset(
            name=f"{dataset.name}:tfidf",
            feature_names=tuple(existing + tfidf_features),
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=fetched_at,
        )
