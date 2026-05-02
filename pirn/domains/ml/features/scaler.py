"""``Scaler`` — fit a scaler on the train split and emit a transformed
:class:`DataSplit` reference.

The actual numeric transformation (standardise / minmax / robust) is
not applied to data here — pirn manipulates references at this layer.
The output is a :class:`DataSplit` whose ``MLDataset`` references are
renamed to record that they have been logically scaled.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, ClassVar, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset


class Scaler(Knot):
    """Apply a logical scaling transformation to every :class:`MLDataset`
    in a :class:`DataSplit`."""

    valid_methods: ClassVar[frozenset[str]] = frozenset(
        {"standardise", "minmax", "robust"}
    )

    def __init__(
        self,
        *,
        split: Knot,
        columns: Sequence[str],
        method: str = "standardise",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        column_tuple = tuple(columns)
        if not column_tuple:
            raise ValueError("Scaler: columns must be non-empty")
        for column in column_tuple:
            if not isinstance(column, str) or not column:
                raise ValueError(
                    "Scaler: every column name must be a non-empty string"
                )
        if method not in self.valid_methods:
            raise ValueError(
                f"Scaler: method must be one of {sorted(self.valid_methods)}"
            )
        self._columns = column_tuple
        self._method = method
        super().__init__(split=split, _config=_config, **kwargs)

    @property
    def method(self) -> str:
        return self._method

    @property
    def columns(self) -> tuple[str, ...]:
        return self._columns

    async def process(self, split: DataSplit, **_: Any) -> DataSplit:
        suffix = f"scaled_{self._method}"
        now = datetime.now(timezone.utc)
        return DataSplit(
            train=self._mark(split.train, suffix, now),
            test=self._mark(split.test, suffix, now),
            validation=(
                self._mark(split.validation, suffix, now)
                if split.validation is not None
                else None
            ),
        )

    def _mark(
        self, dataset: MLDataset, suffix: str, fetched_at: datetime
    ) -> MLDataset:
        return MLDataset(
            name=f"{dataset.name}:{suffix}",
            feature_names=dataset.feature_names,
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=fetched_at,
        )
