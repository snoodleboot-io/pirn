"""``ReconciliationDiff`` — row-level diff between source and target tables.

Hashes every row in both source and target on the specified columns,
outer-joins the hash sets, and classifies each row as:

* ``added``   — present in source but not target.
* ``removed`` — present in target but not source.
* ``changed`` — present in both with different hash (key matches, content differs).
* ``matched`` — identical in both.

Algorithm:
    1. Receive resolved ``source_pool``, ``source_query``, ``target_pool``,
       ``target_query``, ``key_columns``, and ``value_columns`` in ``process()``.
    2. Validate all inputs: pool types, non-empty strings, identifier safety,
       and column disjointness.
    3. Fetch all rows from source and target.
    4. Build hash index for each side: key → MD5(values).
    5. Classify each key as added / removed / changed / matched.
    6. Return result dict with classified lists and counts.

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [2] pirn — IdentifierValidator (SQL injection guard):
        pirn_data/identifier_validator.py
"""

from __future__ import annotations

import hashlib
from typing import Any

from pirn.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.identifier_validator import IdentifierValidator


class ReconciliationDiff(Knot):
    """Row-level reconciliation: hash rows from source and target, classify differences."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        target_query: Knot | str,
        key_columns: Knot | tuple[str, ...],
        value_columns: Knot | tuple[str, ...],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_pool=source_pool,
            source_query=source_query,
            target_pool=target_pool,
            target_query=target_query,
            key_columns=key_columns,
            value_columns=value_columns,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _hash_values(values: tuple[Any, ...]) -> str:
        raw = "|".join(str(v) for v in values)
        return hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()

    @staticmethod
    def _build_index(
        rows: list[Any],
        all_columns: tuple[str, ...],
        key_columns: tuple[str, ...],
        value_columns: tuple[str, ...],
    ) -> dict[tuple[Any, ...], str]:
        index: dict[tuple[Any, ...], str] = {}
        for row in rows:
            row_dict = dict(zip(all_columns, row, strict=False))
            key = tuple(row_dict[k] for k in key_columns)
            val_tuple = tuple(row_dict[k] for k in value_columns)
            index[key] = ReconciliationDiff._hash_values(val_tuple)
        return index

    async def process(
        self,
        *,
        source_pool: Any,
        source_query: Any,
        target_pool: Any,
        target_query: Any,
        key_columns: Any,
        value_columns: Any,
        **_: Any,
    ) -> dict[str, Any]:
        """Hash and diff source vs target rows; classify as added/removed/changed/matched.

        Returns:
            A dict with keys ``succeeded``, ``added``, ``removed``,
            ``changed``, ``matched``, and ``total_differences``.

        Raises:
            TypeError: When source_pool or target_pool is not a DatabaseConnectionPool.
            ValueError: When queries are empty or columns overlap.
        """
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError("ReconciliationDiff: source_pool must be a DatabaseConnectionPool")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("ReconciliationDiff: target_pool must be a DatabaseConnectionPool")
        for label, value in (
            ("source_query", source_query),
            ("target_query", target_query),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"ReconciliationDiff: {label} must be a non-empty string")
        key_tuple = tuple(key_columns)
        value_tuple = tuple(value_columns)
        IdentifierValidator.validate_columns("key_columns", key_tuple)
        IdentifierValidator.validate_columns("value_columns", value_tuple)
        overlap = set(key_tuple) & set(value_tuple)
        if overlap:
            raise ValueError(
                f"ReconciliationDiff: key_columns and value_columns overlap on {sorted(overlap)!r}"
            )
        all_columns = key_tuple + value_tuple
        source_rows = await source_pool.fetch_all(source_query)
        target_rows = await target_pool.fetch_all(target_query)
        source_index = ReconciliationDiff._build_index(
            source_rows, all_columns, key_tuple, value_tuple
        )
        target_index = ReconciliationDiff._build_index(
            target_rows, all_columns, key_tuple, value_tuple
        )
        added = [list(k) for k in source_index if k not in target_index]
        removed = [list(k) for k in target_index if k not in source_index]
        changed = [
            list(k)
            for k in source_index
            if k in target_index and source_index[k] != target_index[k]
        ]
        matched_count = sum(
            1 for k in source_index if k in target_index and source_index[k] == target_index[k]
        )
        total_differences = len(added) + len(removed) + len(changed)
        return {
            "succeeded": True,
            "added": added,
            "removed": removed,
            "changed": changed,
            "matched": matched_count,
            "total_differences": total_differences,
        }
