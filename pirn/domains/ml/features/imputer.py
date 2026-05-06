"""``Imputer`` — missing-value imputation over a :class:`DataSplit`.

Algorithm:
    1. Receive ``split`` (DataSplit), ``columns`` (sequence of str), ``method`` (str),
       and ``constant_value`` (Any) via process().
    2. Validate columns is non-empty, method is valid, and constant_value is set when
       method is ``"constant"``.
    3. Append the ``imputed_<method>`` suffix to each partition's MLDataset name.
    4. Return the renamed DataSplit.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset


class Imputer(Knot):
    """Logical missing-value imputer (mean / median / constant)."""

    valid_methods: ClassVar[frozenset[str]] = frozenset({"mean", "median", "constant"})

    def __init__(
        self,
        *,
        split: Knot,
        columns: Knot | Sequence[str],
        method: Knot | str = "median",
        constant_value: Knot | Any = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            columns=columns,
            method=method,
            constant_value=constant_value,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: DataSplit,
        columns: Sequence[str] = (),
        method: str = "median",
        constant_value: Any = None,
        **_: Any,
    ) -> DataSplit:
        """Apply the configured imputation method to the split's feature columns and return an updated DataSplit.

        Args:
            split: DataSplit whose partitions are logically tagged with the imputation suffix.
            columns: Non-empty sequence of column names to impute.
            method: Imputation method; must be one of ``valid_methods``.
            constant_value: Required when method is ``"constant"``; the fill value.

        Returns:
            DataSplit with each partition renamed to include the ``imputed_<method>`` suffix.

        Raises:
            ValueError: If columns is empty, method is invalid, or constant method has no value.
        """
        column_tuple = tuple(columns)
        if not column_tuple:
            raise ValueError("Imputer: columns must be non-empty")
        for column in column_tuple:
            if not isinstance(column, str) or not column:
                raise ValueError("Imputer: every column name must be a non-empty string")
        if method not in self.valid_methods:
            raise ValueError(f"Imputer: method must be one of {sorted(self.valid_methods)}")
        if method == "constant" and constant_value is None:
            raise ValueError("Imputer: constant method requires constant_value")
        suffix = f"imputed_{method}"
        now = datetime.now(UTC)
        return DataSplit(
            train=self._mark(split.train, suffix, now),
            test=self._mark(split.test, suffix, now),
            validation=(
                self._mark(split.validation, suffix, now) if split.validation is not None else None
            ),
        )

    def _mark(self, dataset: MLDataset, suffix: str, fetched_at: datetime) -> MLDataset:
        return MLDataset(
            name=f"{dataset.name}:{suffix}",
            feature_names=dataset.feature_names,
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=fetched_at,
        )
