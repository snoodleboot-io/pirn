"""``FrequencyEncoder`` — replace each category with its frequency in the
training set.

The encoding is fit on the train partition and applied identically to
all partitions of the :class:`SplitManifest`. Unseen categories in
the test/validation partitions receive ``default_frequency``.

Algorithm:
    1. Receive ``split`` (SplitManifest), ``categorical_column`` (str), and
       ``default_frequency`` (float) via process().
    2. Validate categorical_column and default_frequency.
    3. Apply frequency encoding suffix tag to each partition.
    4. Return updated SplitManifest.

Math:
    freq(c) = count(c in train) / n_train
    Unseen category c' (not in train): freq(c') = default_frequency

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.split_manifest import SplitManifest


class FrequencyEncoder(Knot):
    """Replace a categorical column with per-category training frequencies."""

    def __init__(
        self,
        *,
        split: Knot,
        categorical_column: Knot | str,
        default_frequency: Knot | float = 0.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            categorical_column=categorical_column,
            default_frequency=default_frequency,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: SplitManifest,
        categorical_column: str = "",
        default_frequency: float = 0.0,
        **_: Any,
    ) -> SplitManifest:
        """Apply frequency encoding to the categorical column and return a renamed SplitManifest.

        Args:
            split: SplitManifest whose partitions receive the frequency-encoded suffix.
            categorical_column: Non-empty name of the categorical column.
            default_frequency: Frequency value for unseen categories; must be >= 0.

        Returns:
            SplitManifest with each partition renamed to include the ``freq_encoded`` suffix.

        Raises:
            ValueError: If categorical_column is empty or default_frequency is negative.
        """
        if not isinstance(categorical_column, str) or not categorical_column:
            raise ValueError("FrequencyEncoder: categorical_column must be a non-empty string")
        if not isinstance(default_frequency, (int, float)):
            raise TypeError("FrequencyEncoder: default_frequency must be a number")
        df = float(default_frequency)
        if df < 0.0:
            raise ValueError("FrequencyEncoder: default_frequency must be >= 0.0")
        now = datetime.now(UTC)
        suffix = "freq_encoded"
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
