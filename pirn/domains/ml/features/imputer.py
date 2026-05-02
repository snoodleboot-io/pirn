"""``Imputer`` — missing-value imputation over a :class:`DataSplit`."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, ClassVar, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset


class Imputer(Knot):
    """Logical missing-value imputer (mean / median / constant)."""

    valid_methods: ClassVar[frozenset[str]] = frozenset(
        {"mean", "median", "constant"}
    )

    def __init__(
        self,
        *,
        split: Knot,
        columns: Sequence[str],
        method: str = "median",
        constant_value: Any = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        column_tuple = tuple(columns)
        if not column_tuple:
            raise ValueError("Imputer: columns must be non-empty")
        for column in column_tuple:
            if not isinstance(column, str) or not column:
                raise ValueError(
                    "Imputer: every column name must be a non-empty string"
                )
        if method not in self.valid_methods:
            raise ValueError(
                f"Imputer: method must be one of {sorted(self.valid_methods)}"
            )
        if method == "constant" and constant_value is None:
            raise ValueError(
                "Imputer: constant method requires constant_value"
            )
        self._columns = column_tuple
        self._method = method
        self._constant_value = constant_value
        super().__init__(split=split, _config=_config, **kwargs)

    @property
    def method(self) -> str:
        return self._method

    async def process(self, split: DataSplit, **_: Any) -> DataSplit:
        suffix = f"imputed_{self._method}"
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
