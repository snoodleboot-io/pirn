"""``Encoder`` — categorical encoder over a :class:`SplitManifest`.

Algorithm:
    1. Receive ``split`` (SplitManifest), ``columns`` (sequence of str), and ``method`` (str) via process().
    2. Validate columns is non-empty and all elements are non-empty strings.
    3. Validate method is one of the valid encoding methods.
    4. Append the ``encoded_<method>`` suffix to the name of each partition's DatasetManifest.
    5. Return the renamed SplitManifest.

Math:
    onehot:  for column c with categories {v_1, ..., v_k},
             produce k binary columns: indicator(x == v_j) for j in 1..k
    ordinal: map each category to its rank index in sorted order:
             x_encoded = rank(x) where rank(v_j) = j-1 for sorted v_1..v_k
    target:  x_encoded = mean(y | x == v_j) estimated on the train split

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.split_manifest import SplitManifest


class Encoder(Knot):
    """Logical categorical encoder (onehot / ordinal / target)."""

    valid_methods: ClassVar[frozenset[str]] = frozenset({"onehot", "ordinal", "target"})

    def __init__(
        self,
        *,
        split: Knot,
        columns: Knot | Sequence[str],
        method: Knot | str = "onehot",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(split=split, columns=columns, method=method, _config=_config, **kwargs)

    async def process(
        self,
        split: SplitManifest,
        columns: Sequence[str] = (),
        method: str = "onehot",
        **_: Any,
    ) -> SplitManifest:
        """Apply the configured categorical encoding method to the split and return a renamed SplitManifest.

        Args:
            split: SplitManifest whose partitions are logically tagged with the encoding suffix.
            columns: Non-empty sequence of column names to encode.
            method: Encoding method; must be one of ``valid_methods``.

        Returns:
            SplitManifest with each partition renamed to include the ``encoded_<method>`` suffix.

        Raises:
            ValueError: If columns is empty, any element is empty, or method is invalid.
        """
        column_tuple = tuple(columns)
        if not column_tuple:
            raise ValueError("Encoder: columns must be non-empty")
        for column in column_tuple:
            if not isinstance(column, str) or not column:
                raise ValueError("Encoder: every column name must be a non-empty string")
        if method not in self.valid_methods:
            raise ValueError(f"Encoder: method must be one of {sorted(self.valid_methods)}")
        suffix = f"encoded_{method}"
        now = datetime.now(UTC)
        return SplitManifest(
            train=self._mark(split.train, suffix, now),
            test=self._mark(split.test, suffix, now),
            validation=(
                self._mark(split.validation, suffix, now) if split.validation is not None else None
            ),
        )

    def _mark(self, dataset: DatasetManifest, suffix: str, fetched_at: datetime) -> DatasetManifest:
        return DatasetManifest(
            name=f"{dataset.name}:{suffix}",
            feature_names=dataset.feature_names,
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=fetched_at,
        )
