"""``NGramExtractor`` — extract character or word n-grams from a text column.

Appends ``ngram_<analyzer>_<n>_<i>`` feature names for each of the
``max_features`` n-gram dimensions. The ``analyzer`` parameter selects
``"char"`` or ``"word"`` n-grams.

Algorithm:
    1. Receive ``split`` (SplitManifest), ``text_column``, ``n``, ``analyzer``,
       and ``max_features`` via process().
    2. Validate all inputs.
    3. Remove the original text column and append ngram feature names.
    4. Return updated SplitManifest.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.split_manifest import SplitManifest


class NGramExtractor(Knot):
    """Append n-gram feature names for a text column."""

    valid_analyzers: ClassVar[frozenset[str]] = frozenset({"char", "word"})

    def __init__(
        self,
        *,
        split: Knot,
        text_column: Knot | str,
        n: Knot | int = 2,
        analyzer: Knot | str = "word",
        max_features: Knot | int = 50,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            text_column=text_column,
            n=n,
            analyzer=analyzer,
            max_features=max_features,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: SplitManifest,
        text_column: str = "",
        n: int = 2,
        analyzer: str = "word",
        max_features: int = 50,
        **_: Any,
    ) -> SplitManifest:
        """Append n-gram feature names for the text column to every partition.

        Args:
            split: SplitManifest whose partitions receive the n-gram feature names.
            text_column: Non-empty name of the text column.
            n: N-gram size; must be an int >= 1.
            analyzer: Must be one of {"char", "word"}.
            max_features: Number of n-gram dimensions; must be an int >= 1.

        Returns:
            SplitManifest with ``ngram_<analyzer>_<n>_<i>`` feature names appended
            to every partition, and the original text column removed.

        Raises:
            ValueError: If any input fails validation.
        """
        if not isinstance(text_column, str) or not text_column:
            raise ValueError("NGramExtractor: text_column must be a non-empty string")
        if not isinstance(n, int):
            raise TypeError("NGramExtractor: n must be an int")
        if n < 1:
            raise ValueError("NGramExtractor: n must be >= 1")
        if analyzer not in self.valid_analyzers:
            raise ValueError(
                f"NGramExtractor: analyzer must be one of {sorted(self.valid_analyzers)}"
            )
        if not isinstance(max_features, int):
            raise TypeError("NGramExtractor: max_features must be an int")
        if max_features < 1:
            raise ValueError("NGramExtractor: max_features must be >= 1")
        now = datetime.now(UTC)
        return SplitManifest(
            train=self._add_ngram_features(
                split.train, text_column, n, analyzer, max_features, now
            ),
            test=self._add_ngram_features(split.test, text_column, n, analyzer, max_features, now),
            validation=(
                self._add_ngram_features(
                    split.validation, text_column, n, analyzer, max_features, now
                )
                if split.validation is not None
                else None
            ),
        )

    def _add_ngram_features(
        self,
        dataset: DatasetManifest,
        text_column: str,
        n: int,
        analyzer: str,
        max_features: int,
        fetched_at: datetime,
    ) -> DatasetManifest:
        existing = [f for f in dataset.feature_names if f != text_column]
        ngram_features = [f"ngram_{analyzer}_{n}_{i}" for i in range(max_features)]
        return DatasetManifest(
            name=f"{dataset.name}:ngram_{analyzer}_{n}",
            feature_names=tuple(existing + ngram_features),
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=fetched_at,
        )
