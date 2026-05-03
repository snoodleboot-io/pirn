"""``ReconciliationDiff`` — row-level diff between source and target tables.

Hashes every row in both source and target on the specified columns,
outer-joins the hash sets, and classifies each row as:

* ``added``   — present in source but not target.
* ``removed`` — present in target but not source.
* ``changed`` — present in both with different hash (key matches, content differs).
* ``matched`` — identical in both.
"""

from __future__ import annotations

import hashlib
from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class ReconciliationDiff(SubTapestry):
    """Row-level reconciliation: hash rows from source and target, classify differences."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_query: str,
        target_pool: DatabaseConnectionPool,
        target_query: str,
        key_columns: Sequence[str],
        value_columns: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "ReconciliationDiff: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "ReconciliationDiff: target_pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_query", source_query),
            ("target_query", target_query),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"ReconciliationDiff: {label} must be a non-empty string"
                )
        key_tuple = tuple(key_columns)
        value_tuple = tuple(value_columns)
        IdentifierValidator.validate_columns("key_columns", key_tuple)
        IdentifierValidator.validate_columns("value_columns", value_tuple)
        overlap = set(key_tuple) & set(value_tuple)
        if overlap:
            raise ValueError(
                f"ReconciliationDiff: key_columns and value_columns overlap "
                f"on {sorted(overlap)!r}"
            )
        self._source_pool = source_pool
        self._source_query = source_query
        self._target_pool = target_pool
        self._target_query = target_query
        self._key_columns = key_tuple
        self._value_columns = value_tuple
        self._all_columns = key_tuple + value_tuple
        super().__init__(_config=_config, **kwargs)

    def _hash_values(self, values: tuple[Any, ...]) -> str:
        raw = "|".join(str(v) for v in values)
        return hashlib.md5(raw.encode()).hexdigest()

    def _build_index(
        self, rows: list[Any]
    ) -> dict[tuple[Any, ...], str]:
        index: dict[tuple[Any, ...], str] = {}
        for row in rows:
            row_dict = dict(zip(self._all_columns, row))
            key = tuple(row_dict[k] for k in self._key_columns)
            value_tuple = tuple(row_dict[k] for k in self._value_columns)
            index[key] = self._hash_values(value_tuple)
        return index

    async def process(self, **_: Any) -> dict[str, Any]:
        """Hash and diff source vs target rows; classify as added/removed/changed/matched.

        Returns:
            A dict with keys ``succeeded``, ``added``, ``removed``,
            ``changed``, ``matched``, and ``total_differences``.
        """
        source_rows = await self._source_pool.fetch_all(self._source_query)
        target_rows = await self._target_pool.fetch_all(self._target_query)
        source_index = self._build_index(source_rows)
        target_index = self._build_index(target_rows)
        added = [list(k) for k in source_index if k not in target_index]
        removed = [list(k) for k in target_index if k not in source_index]
        changed = [
            list(k)
            for k in source_index
            if k in target_index and source_index[k] != target_index[k]
        ]
        matched_count = sum(
            1
            for k in source_index
            if k in target_index and source_index[k] == target_index[k]
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
