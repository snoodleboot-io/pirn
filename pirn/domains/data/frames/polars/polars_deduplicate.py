"""``PolarsDeduplicate`` — Tier-2 dedup via :meth:`polars.DataFrame.unique`.

First-occurrence wins on the configured key columns, mirroring the
Tier-1 :class:`Deduplicate` semantics. Polars handles the heavy lifting
(hash-based, vectorised) so this works on large frames without
materialising row dicts.

Algorithm:
    1. Validate ``keys`` as a non-empty sequence of non-empty strings.
    2. Call ``frame.unique(subset=list(keys), keep="first",
       maintain_order=True)`` to drop duplicates while preserving the
       original row order of the first occurrences.
    3. Return the deduplicated frame wrapped in a new
       :class:`PolarsDataBatch`.

References:
    [1] Polars — DataFrame.unique:
        https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.unique.html
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch


class PolarsDeduplicate(Knot):
    """Drop duplicate rows by key tuple, keeping the first occurrence."""

    def __init__(
        self,
        *,
        batch: Knot,
        keys: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, keys=keys, _config=_config, **kwargs)

    async def process(
        self,
        batch: PolarsDataBatch,
        keys: Any,
        **_: Any,
    ) -> PolarsDataBatch:
        """Drop duplicate rows by key columns, keeping the first occurrence.

        Args:
            batch: The upstream PolarsDataBatch to deduplicate.
            keys: Sequence of column names that form the deduplication key.

        Returns:
            A new PolarsDataBatch with duplicate key-tuple rows removed.
        """
        if not isinstance(keys, Sequence) or isinstance(keys, (str, bytes)):
            raise TypeError("PolarsDeduplicate: keys must be a sequence of column names")
        if not keys:
            raise ValueError("PolarsDeduplicate: keys must be non-empty")
        for key in keys:
            if not isinstance(key, str) or not key:
                raise TypeError("PolarsDeduplicate: every entry in keys must be a non-empty string")
        return batch.with_frame(
            batch.frame.unique(subset=list(keys), keep="first", maintain_order=True)
        )
