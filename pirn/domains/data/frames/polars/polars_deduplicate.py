"""``PolarsDeduplicate`` — Tier-2 dedup via :meth:`polars.DataFrame.unique`.

First-occurrence wins on the configured key columns, mirroring the
Tier-1 :class:`Deduplicate` semantics. Polars handles the heavy lifting
(hash-based, vectorised) so this works on large frames without
materialising row dicts.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch


class PolarsDeduplicate(Knot):
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
                "PolarsDeduplicate: keys must be a sequence of column names"
            )
        if not keys:
            raise ValueError("PolarsDeduplicate: keys must be non-empty")
        for key in keys:
            if not isinstance(key, str) or not key:
                raise TypeError(
                    "PolarsDeduplicate: every entry in keys must be a non-empty string"
                )
        self._keys: tuple[str, ...] = tuple(keys)
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def keys(self) -> tuple[str, ...]:
        return self._keys

    async def process(self, batch: PolarsDataBatch, **_: Any) -> PolarsDataBatch:
        return batch.with_frame(
            batch.frame.unique(subset=list(self._keys), keep="first", maintain_order=True)
        )
