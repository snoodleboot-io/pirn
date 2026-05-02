"""``PolynomialFeatures`` — emit polynomial / interaction feature names."""

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
        columns: Sequence[str],
        degree: int = 2,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
        self._columns = column_tuple
        self._degree = degree
        super().__init__(split=split, _config=_config, **kwargs)

    @property
    def degree(self) -> int:
        return self._degree

    async def process(self, split: DataSplit, **_: Any) -> DataSplit:
        new_features = self._derive_feature_names()
        now = datetime.now(timezone.utc)
        return DataSplit(
            train=self._extend(split.train, new_features, now),
            test=self._extend(split.test, new_features, now),
            validation=(
                self._extend(split.validation, new_features, now)
                if split.validation is not None
                else None
            ),
        )

    def _derive_feature_names(self) -> tuple[str, ...]:
        names: list[str] = []
        for current_degree in range(2, self._degree + 1):
            for combo in combinations_with_replacement(
                self._columns, current_degree
            ):
                names.append("*".join(combo))
        return tuple(names)

    def _extend(
        self,
        dataset: MLDataset,
        new_features: tuple[str, ...],
        fetched_at: datetime,
    ) -> MLDataset:
        merged: list[str] = list(dataset.feature_names)
        for feature in new_features:
            if feature not in merged:
                merged.append(feature)
        return MLDataset(
            name=f"{dataset.name}:poly{self._degree}",
            feature_names=tuple(merged),
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=fetched_at,
        )
