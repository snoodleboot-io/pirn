"""``PandasDeduplicate`` — Tier-2 dedup via
:meth:`pandas.DataFrame.drop_duplicates`.

First-occurrence wins on the configured key columns, mirroring the
Tier-1 :class:`Deduplicate` semantics.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.pandas.pandas_data_batch import PandasDataBatch


class PandasDeduplicate(Knot):
    """Drop duplicate rows by key tuple, keeping the first occurrence."""

    def __init__(
        self,
        *,
        batch: Knot,
        keys: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(keys, Sequence) or isinstance(keys, (str, bytes)):
            raise TypeError(
                "PandasDeduplicate: keys must be a sequence of column names"
            )
        if not keys:
            raise ValueError("PandasDeduplicate: keys must be non-empty")
        for key in keys:
            if not isinstance(key, str) or not key:
                raise TypeError(
                    "PandasDeduplicate: every entry in keys must be a non-empty string"
                )
        self._keys: tuple[str, ...] = tuple(keys)
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def keys(self) -> tuple[str, ...]:
        return self._keys

    async def process(self, batch: PandasDataBatch, **_: Any) -> PandasDataBatch:
        """Drop duplicate rows by key columns, keeping the first occurrence.

        Args:
            batch: The PandasDataBatch to deduplicate.

        Returns:
            A new PandasDataBatch with duplicate rows removed, retaining the first occurrence per key.
        """
        deduped = batch.frame.drop_duplicates(
            subset=list(self._keys), keep="first"
        ).reset_index(drop=True)
        return batch.with_frame(deduped)
