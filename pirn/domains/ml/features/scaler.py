"""``Scaler`` — fit a scaler on the train split and emit a transformed
:class:`DataSplit` reference.

The actual numeric transformation (standardise / minmax / robust) is
not applied to data here — pirn manipulates references at this layer.
The output is a :class:`DataSplit` whose ``MLDataset`` references are
renamed to record that they have been logically scaled.

Algorithm:
    1. Receive ``split`` (DataSplit), ``columns`` (sequence of str), and ``method`` (str) via process().
    2. Validate columns is non-empty and method is valid.
    3. Append the ``scaled_<method>`` suffix to each partition's MLDataset name.
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
        columns: Knot | Sequence[str],
        method: Knot | str = "standardise",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(split=split, columns=columns, method=method, _config=_config, **kwargs)

    async def process(
        self,
        split: DataSplit,
        columns: Sequence[str] = (),
        method: str = "standardise",
        **_: Any,
    ) -> DataSplit:
        """Logically scale each partition's MLDataset using the configured method and return the renamed DataSplit.

        Args:
            split: DataSplit whose partitions are logically tagged with the scaling suffix.
            columns: Non-empty sequence of column names to scale.
            method: Scaling method; must be one of ``valid_methods``.

        Returns:
            DataSplit with each partition renamed to include the ``scaled_<method>`` suffix.

        Raises:
            ValueError: If columns is empty or method is invalid.
        """
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
        suffix = f"scaled_{method}"
        now = datetime.now(UTC)
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
