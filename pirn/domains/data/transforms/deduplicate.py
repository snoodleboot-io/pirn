"""``Deduplicate`` — drop duplicate rows based on a tuple of key columns.

The first occurrence wins; subsequent rows with the same key tuple are
discarded. Order of the surviving rows mirrors their original order in
the batch.

For semantic dedup beyond exact key equality (fuzzy match on names,
proximity match on coordinates, etc.) see the dedicated specialisation
knots in `pirn.domains.data.specializations.dedup`.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch


class Deduplicate(Knot):
    """Drop rows whose ``(keys[0], keys[1], …)`` tuple has already been seen."""

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
                "Deduplicate: keys must be a sequence of column names "
                "(e.g. tuple or list)"
            )
        if not keys:
            raise ValueError("Deduplicate: keys must be non-empty")
        for k in keys:
            if not isinstance(k, str) or not k:
                raise TypeError(
                    "Deduplicate: every entry in keys must be a non-empty string"
                )
        self._keys: tuple[str, ...] = tuple(keys)
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def keys(self) -> tuple[str, ...]:
        return self._keys

    async def process(self, batch: DataBatch, **_: Any) -> DataBatch:
        seen: set[tuple[Any, ...]] = set()
        kept: list[Mapping[str, Any]] = []
        for row in batch.rows:
            key = self._row_key(row)
            if key in seen:
                continue
            seen.add(key)
            kept.append(row)
        return batch.with_rows(tuple(kept))

    def _row_key(self, row: Mapping[str, Any]) -> tuple[Any, ...]:
        return tuple(self._hashable(row.get(k)) for k in self._keys)

    @staticmethod
    def _hashable(value: Any) -> Any:
        try:
            hash(value)
            return value
        except TypeError:
            return repr(value)
