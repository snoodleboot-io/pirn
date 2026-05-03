"""``NGramExtractor`` — extract character or word n-grams from a text column.

Appends ``ngram_<analyzer>_<n>_<i>`` feature names for each of the
``max_features`` n-gram dimensions. The ``analyzer`` parameter selects
``"char"`` or ``"word"`` n-grams.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset


class NGramExtractor(Knot):
    """Append n-gram feature names for a text column."""

    valid_analyzers: ClassVar[frozenset[str]] = frozenset({"char", "word"})

    def __init__(
        self,
        *,
        split: Knot,
        text_column: str,
        n: int = 2,
        analyzer: str = "word",
        max_features: int = 50,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(split, Knot):
            raise TypeError("NGramExtractor: split must be a Knot")
        if not isinstance(text_column, str) or not text_column:
            raise ValueError(
                "NGramExtractor: text_column must be a non-empty string"
            )
        if not isinstance(n, int):
            raise TypeError("NGramExtractor: n must be an int")
        if n < 1:
            raise ValueError("NGramExtractor: n must be >= 1")
        if analyzer not in self.valid_analyzers:
            raise ValueError(
                f"NGramExtractor: analyzer must be one of "
                f"{sorted(self.valid_analyzers)}"
            )
        if not isinstance(max_features, int):
            raise TypeError("NGramExtractor: max_features must be an int")
        if max_features < 1:
            raise ValueError("NGramExtractor: max_features must be >= 1")
        self._text_column = text_column
        self._n = n
        self._analyzer = analyzer
        self._max_features = max_features
        super().__init__(split=split, _config=_config, **kwargs)

    @property
    def n(self) -> int:
        return self._n

    @property
    def analyzer(self) -> str:
        return self._analyzer

    async def process(self, split: DataSplit, **_: Any) -> DataSplit:
        """Append n-gram feature names for the text column to every partition.

        Args:
            split: DataSplit whose partitions receive the n-gram feature names.

        Returns:
            DataSplit with ``ngram_<analyzer>_<n>_<i>`` feature names appended
            to every partition, and the original text column removed.
        """
        now = datetime.now(timezone.utc)
        return DataSplit(
            train=self._add_ngram_features(split.train, now),
            test=self._add_ngram_features(split.test, now),
            validation=(
                self._add_ngram_features(split.validation, now)
                if split.validation is not None
                else None
            ),
        )

    def _add_ngram_features(
        self, dataset: MLDataset, fetched_at: datetime
    ) -> MLDataset:
        existing = [
            f for f in dataset.feature_names if f != self._text_column
        ]
        ngram_features = [
            f"ngram_{self._analyzer}_{self._n}_{i}"
            for i in range(self._max_features)
        ]
        return MLDataset(
            name=f"{dataset.name}:ngram_{self._analyzer}_{self._n}",
            feature_names=tuple(existing + ngram_features),
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=fetched_at,
        )
