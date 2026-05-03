"""``Sampler`` — subsample an :class:`MLDataset` reference.

Like the other data-prep knots, this one operates on the
:class:`MLDataset` reference rather than the underlying rows; the
output ``row_count`` is reduced according to ``n`` or ``fraction`` and
the source uri / feature schema are preserved.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.ml_dataset import MLDataset


class Sampler(Knot):
    """Reduce an :class:`MLDataset` to ``n`` rows or ``fraction`` of rows."""

    def __init__(
        self,
        *,
        dataset: Knot,
        n: int | None = None,
        fraction: float | None = None,
        stratify_column: str | None = None,
        random_seed: int = 42,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if (n is None) == (fraction is None):
            raise ValueError(
                "Sampler: provide exactly one of n or fraction"
            )
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
            raise ValueError(
                "Sampler: stratify_column must be a non-empty string"
            )
        if not isinstance(random_seed, int):
            raise TypeError("Sampler: random_seed must be an int")
        self._n = n
        self._fraction = float(fraction) if fraction is not None else None
        self._stratify_column = stratify_column
        self._random_seed = random_seed
        super().__init__(dataset=dataset, _config=_config, **kwargs)

    async def process(self, dataset: MLDataset, **_: Any) -> MLDataset:
        """Reduce the dataset reference row count to the configured n or fraction and return the sampled reference.

        Args:
            dataset: MLDataset reference to downsample.

        Returns:
            MLDataset reference with row_count reduced according to n or fraction.
        """
        total = int(dataset.row_count)
        if self._n is not None:
            row_count = min(self._n, total)
        else:
            row_count = max(1, int(total * (self._fraction or 0.0)))
        return MLDataset(
            name=f"{dataset.name}:sampled",
            feature_names=dataset.feature_names,
            target_name=dataset.target_name,
            row_count=row_count,
            source_uri=dataset.source_uri,
            fetched_at=datetime.now(timezone.utc),
        )
