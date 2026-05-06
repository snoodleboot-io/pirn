"""``Deduplicate`` — drop duplicate rows based on a tuple of key columns.

The first occurrence wins; subsequent rows with the same key tuple are
discarded. Order of the surviving rows mirrors their original order in
the batch.

For semantic dedup beyond exact key equality (fuzzy match on names,
proximity match on coordinates, etc.) see the dedicated specialisation
knots in `pirn.domains.data.specializations.dedup`.

Algorithm:
    1. Validate ``keys``: must be a non-empty sequence (not a bare string)
       of non-empty strings.
    2. Iterate over the rows in order. For each row, form a key tuple from
       the values at the configured columns. Unhashable values (e.g. lists)
       are coerced to their ``repr`` so they can participate in the seen-set
       without crashing.
    3. If the key tuple is already in the seen-set, skip the row. Otherwise,
       add it to the seen-set and keep the row.
    4. Return a new batch containing only the kept rows in their original
       order; the schema is preserved unchanged.

    ```text
    seen = set()
    for row in rows:
        key = tuple(hashable(row[k]) for k in keys)
        if key not in seen:
            seen.add(key)
            emit row
    ```

References:
    [1] Python ``dict`` insertion-order guarantee (Python ≥ 3.7) — alternative
        implementation using ``dict.fromkeys`` on the key tuples (not used here
        because rows are mappings, not scalars):
        https://docs.python.org/3/library/stdtypes.html#dict
    [2] dbt ``unique`` generic test — canonical deduplication check pattern in
        the data warehouse community:
        https://docs.getdbt.com/docs/build/data-tests#unique
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch


class Deduplicate(Knot):
    """Drop rows whose ``(keys[0], keys[1], …)`` tuple has already been seen."""

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
        batch: DataBatch,
        keys: Any,
        **_: Any,
    ) -> DataBatch:
        """Drop rows whose key tuple has already been seen, keeping the first occurrence.

        Args:
            batch: The DataBatch to deduplicate.
            keys: Sequence of column names forming the deduplication key.

        Returns:
            A new DataBatch with duplicate rows removed, preserving original row order.
        """
        if not isinstance(keys, Sequence) or isinstance(keys, (str, bytes)):
            raise TypeError(
                "Deduplicate: keys must be a sequence of column names (e.g. tuple or list)"
            )
        if not keys:
            raise ValueError("Deduplicate: keys must be non-empty")
        for k in keys:
            if not isinstance(k, str) or not k:
                raise TypeError("Deduplicate: every entry in keys must be a non-empty string")
        keys_tuple: tuple[str, ...] = tuple(keys)
        seen: set[tuple[Any, ...]] = set()
        kept: list[Mapping[str, Any]] = []
        for row in batch.rows:
            key = self._row_key(row, keys_tuple)
            if key in seen:
                continue
            seen.add(key)
            kept.append(row)
        return batch.with_rows(tuple(kept))

    @staticmethod
    def _row_key(row: Mapping[str, Any], keys: tuple[str, ...]) -> tuple[Any, ...]:
        return tuple(Deduplicate._hashable(row.get(k)) for k in keys)

    @staticmethod
    def _hashable(value: Any) -> Any:
        try:
            hash(value)
            return value
        except TypeError:
            return repr(value)
