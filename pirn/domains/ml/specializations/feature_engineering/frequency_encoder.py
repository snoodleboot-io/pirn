"""``FrequencyEncoder`` — replace each category with its frequency in the
training set.

The encoding is fit on the train partition and applied identically to
all partitions of the :class:`DataSplit`. Unseen categories in
the test/validation partitions receive ``default_frequency``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset


class FrequencyEncoder(Knot):
    """Replace a categorical column with per-category training frequencies."""

    def __init__(
        self,
        *,
        split: Knot,
        categorical_column: str,
        default_frequency: float = 0.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(categorical_column, str) or not categorical_column:
            raise ValueError(
                "FrequencyEncoder: categorical_column must be a non-empty "
                "string"
            )
        if not isinstance(default_frequency, (int, float)):
            raise TypeError(
                "FrequencyEncoder: default_frequency must be a number"
            )
        if float(default_frequency) < 0.0:
            raise ValueError(
                "FrequencyEncoder: default_frequency must be >= 0.0"
            )
        self._categorical_column = categorical_column
        self._default_frequency = float(default_frequency)
        super().__init__(split=split, _config=_config, **kwargs)

    @property
    def default_frequency(self) -> float:
        return self._default_frequency

    async def process(self, split: DataSplit, **_: Any) -> DataSplit:
        """Apply frequency encoding to the categorical column and return a renamed DataSplit.

        Args:
            split: DataSplit whose partitions receive the frequency-encoded suffix.

        Returns:
            DataSplit with each partition renamed to include the ``freq_encoded`` suffix.
        """
        now = datetime.now(timezone.utc)
        suffix = "freq_encoded"
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
