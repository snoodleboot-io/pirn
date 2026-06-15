"""``PandasDeduplicate`` — Tier-2 dedup via
:meth:`pandas.DataFrame.drop_duplicates`.

First-occurrence wins on the configured key columns, mirroring the
Tier-1 :class:`Deduplicate` semantics.

Algorithm:
    1. Validate ``keys`` as a non-empty sequence of non-empty strings.
    2. Call ``frame.drop_duplicates(subset=list(keys), keep="first")``
       to retain the first occurrence of each unique key tuple.
    3. Reset the integer index so row numbers are contiguous.
    4. Return the deduplicated frame wrapped in a new
       :class:`PandasDataBatch`.

    ```text
    deduped = frame.drop_duplicates(subset=keys, keep="first")
    return batch.with_frame(deduped.reset_index(drop=True))
    ```

References:
    [1] pandas — DataFrame.drop_duplicates:
        https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.drop_duplicates.html
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.frames.pandas.pandas_data_batch import PandasDataBatch


class PandasDeduplicate(Knot):
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
        batch: PandasDataBatch,
        keys: Any,
        **_: Any,
    ) -> PandasDataBatch:
        """Drop duplicate rows by key columns, keeping the first occurrence.

        Args:
            batch: The PandasDataBatch to deduplicate.
            keys: Sequence of column names that form the deduplication key.

        Returns:
            A new PandasDataBatch with duplicate rows removed, keeping the first occurrence per key.
        """
        if not isinstance(keys, Sequence) or isinstance(keys, (str, bytes)):
            raise TypeError("PandasDeduplicate: keys must be a sequence of column names")
        if not keys:
            raise ValueError("PandasDeduplicate: keys must be non-empty")
        for key in keys:
            if not isinstance(key, str) or not key:
                raise TypeError("PandasDeduplicate: every entry in keys must be a non-empty string")
        deduped = batch.frame.drop_duplicates(subset=list(keys), keep="first").reset_index(
            drop=True
        )
        return batch.with_frame(deduped)
