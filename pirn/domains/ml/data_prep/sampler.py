"""``Sampler`` — subsample an :class:`DatasetManifest` reference.

Like the other data-prep knots, this one operates on the
:class:`DatasetManifest` reference rather than the underlying rows; the
output ``row_count`` is reduced according to ``n`` or ``fraction`` and
the source uri / feature schema are preserved.

Algorithm:
    1. Receive ``dataset``, ``n``, ``fraction``, ``stratify_column``, and
       ``random_seed`` via process().
    2. Validate that exactly one of ``n`` or ``fraction`` is provided.
    3. Compute new row_count: min(n, total) when n is set; else max(1, int(total * fraction)).
    4. Return a renamed DatasetManifest reference with the reduced row_count.

Math:
    row_count = min(n, total)              [when n is provided]
    row_count = max(1, int(total * frac))  [when fraction is provided]

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.dataset_manifest import DatasetManifest


class Sampler(Knot):
    """Reduce an :class:`DatasetManifest` to ``n`` rows or ``fraction`` of rows."""

    def __init__(
        self,
        *,
        dataset: Knot,
        n: Knot | int | None = None,
        fraction: Knot | float | None = None,
        stratify_column: Knot | str | None = None,
        random_seed: Knot | int = 42,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            dataset=dataset,
            n=n,
            fraction=fraction,
            stratify_column=stratify_column,
            random_seed=random_seed,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        dataset: DatasetManifest,
        n: int | None = None,
        fraction: float | None = None,
        stratify_column: str | None = None,
        random_seed: int = 42,
        **_: Any,
    ) -> DatasetManifest:
        """Reduce the dataset reference row count to the configured n or fraction and return the sampled reference.

        Args:
            dataset: DatasetManifest reference to downsample.
            n: Absolute row count ceiling; mutually exclusive with fraction.
            fraction: Fraction of rows to keep in (0, 1]; mutually exclusive with n.
            stratify_column: Optional column name for stratified sampling metadata.
            random_seed: Random seed (reserved for future shuffle logic).

        Returns:
            DatasetManifest reference with row_count reduced according to n or fraction.

        Raises:
            ValueError: If both or neither of n/fraction are provided, or values are out of range.
            TypeError: If n, fraction, or random_seed have wrong types.
        """
        if (n is None) == (fraction is None):
            raise ValueError("Sampler: provide exactly one of n or fraction")
        if n is not None:
            if not isinstance(n, int):
                raise TypeError("Sampler: n must be an int")
            if n <= 0:
                raise ValueError("Sampler: n must be positive")
        if fraction is not None:
            if not isinstance(fraction, (int, float)):
                raise TypeError("Sampler: fraction must be numeric")
            if fraction <= 0.0 or fraction > 1.0:
                raise ValueError("Sampler: fraction must be in (0, 1]")
        if stratify_column is not None and (
            not isinstance(stratify_column, str) or not stratify_column
        ):
            raise ValueError("Sampler: stratify_column must be a non-empty string")
        if not isinstance(random_seed, int):
            raise TypeError("Sampler: random_seed must be an int")
        total = int(dataset.row_count)
        if n is not None:
            row_count = min(n, total)
        else:
            row_count = max(1, int(total * (fraction or 0.0)))
        return DatasetManifest(
            name=f"{dataset.name}:sampled",
            feature_names=dataset.feature_names,
            target_name=dataset.target_name,
            row_count=row_count,
            source_uri=dataset.source_uri,
            fetched_at=datetime.now(UTC),
        )
