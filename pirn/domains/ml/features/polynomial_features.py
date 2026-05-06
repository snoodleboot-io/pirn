"""``PolynomialFeatures`` — emit polynomial / interaction feature names.

Algorithm:
    1. Receive ``split`` (DataSplit), ``columns`` (sequence of str), and ``degree`` (int) via process().
    2. Validate columns is non-empty and degree >= 2.
    3. Enumerate combinations_with_replacement for degrees 2..degree across columns.
    4. Append the new feature names to each partition's feature list.
    5. Return the augmented DataSplit.

Math:
    new_features = {col_i * col_j * ... (d terms) | d in 2..degree, cols from columns}

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from itertools import combinations_with_replacement
from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset


class PolynomialFeatures(Knot):
    """Augment a :class:`DataSplit` with polynomial / interaction features."""

    def __init__(
        self,
        *,
        split: Knot,
        columns: Knot | Sequence[str],
        degree: Knot | int = 2,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(split=split, columns=columns, degree=degree, _config=_config, **kwargs)

    async def process(
        self,
        split: DataSplit,
        columns: Sequence[str] = (),
        degree: int = 2,
        **_: Any,
    ) -> DataSplit:
        """Derive polynomial and interaction feature names from the configured columns and return an augmented DataSplit.

        Args:
            split: DataSplit whose partitions receive the new polynomial feature names.
            columns: Non-empty sequence of base feature column names.
            degree: Polynomial degree; must be an int >= 2.

        Returns:
            DataSplit with polynomial and interaction feature names appended to every partition.

        Raises:
            ValueError: If columns is empty or any element is empty.
            TypeError: If degree is not an int.
            ValueError: If degree < 2.
        """
        column_tuple = tuple(columns)
        if not column_tuple:
            raise ValueError("PolynomialFeatures: columns must be non-empty")
        for column in column_tuple:
            if not isinstance(column, str) or not column:
                raise ValueError(
                    "PolynomialFeatures: every column name must be a "
                    "non-empty string"
                )
        if not isinstance(degree, int):
            raise TypeError("PolynomialFeatures: degree must be an int")
        if degree < 2:
            raise ValueError("PolynomialFeatures: degree must be >= 2")
        new_features = self._derive_feature_names(column_tuple, degree)
        now = datetime.now(timezone.utc)
        return DataSplit(
            train=self._extend(split.train, new_features, degree, now),
            test=self._extend(split.test, new_features, degree, now),
            validation=(
                self._extend(split.validation, new_features, degree, now)
                if split.validation is not None
                else None
            ),
        )

    def _derive_feature_names(
        self, columns: tuple[str, ...], degree: int
    ) -> tuple[str, ...]:
        names: list[str] = []
        for current_degree in range(2, degree + 1):
            for combo in combinations_with_replacement(columns, current_degree):
                names.append("*".join(combo))
        return tuple(names)

    def _extend(
        self,
        dataset: MLDataset,
        new_features: tuple[str, ...],
        degree: int,
        fetched_at: datetime,
    ) -> MLDataset:
        merged: list[str] = list(dataset.feature_names)
        for feature in new_features:
            if feature not in merged:
                merged.append(feature)
        return MLDataset(
            name=f"{dataset.name}:poly{degree}",
            feature_names=tuple(merged),
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=fetched_at,
        )
