"""``Scaler`` — fit a scaler on the train split and emit a transformed
:class:`SplitManifest` reference.

The actual numeric transformation (standardise / minmax / robust) is
not applied to data here — pirn manipulates references at this layer.
The output is a :class:`SplitManifest` whose ``DatasetManifest`` references are
renamed to record that they have been logically scaled.

Algorithm:
    1. Receive ``split`` (SplitManifest), ``columns`` (sequence of str), and ``method`` (str) via process().
    2. Validate columns is non-empty and method is valid.
    3. Append the ``scaled_<method>`` suffix to each partition's DatasetManifest name.
    4. Return the renamed SplitManifest.

Math:
    standardise (z-score): x_scaled = (x - mu) / sigma
        where mu = mean(x_train), sigma = std(x_train)
    minmax:   x_scaled = (x - x_min) / (x_max - x_min)
        where x_min, x_max are computed on x_train
    robust:   x_scaled = (x - median(x_train)) / IQR(x_train)
        where IQR = Q3 - Q1 computed on x_train

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.split_manifest import SplitManifest


class Scaler(Knot):
    """Apply a logical scaling transformation to every :class:`DatasetManifest`
    in a :class:`SplitManifest`."""

    valid_methods: ClassVar[frozenset[str]] = frozenset({"standardise", "minmax", "robust"})

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
        split: SplitManifest,
        columns: Sequence[str] = (),
        method: str = "standardise",
        **_: Any,
    ) -> SplitManifest:
        """Logically scale each partition's DatasetManifest using the configured method and return the renamed SplitManifest.

        Args:
            split: SplitManifest whose partitions are logically tagged with the scaling suffix.
            columns: Non-empty sequence of column names to scale.
            method: Scaling method; must be one of ``valid_methods``.

        Returns:
            SplitManifest with each partition renamed to include the ``scaled_<method>`` suffix.

        Raises:
            ValueError: If columns is empty or method is invalid.
        """
        column_tuple = tuple(columns)
        if not column_tuple:
            raise ValueError("Scaler: columns must be non-empty")
        for column in column_tuple:
            if not isinstance(column, str) or not column:
                raise ValueError("Scaler: every column name must be a non-empty string")
        if method not in self.valid_methods:
            raise ValueError(f"Scaler: method must be one of {sorted(self.valid_methods)}")
        suffix = f"scaled_{method}"
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
