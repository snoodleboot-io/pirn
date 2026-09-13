"""``_PoolMergeKnot`` — shared validation and merge helpers for pool-backed
SCD and upsert knots.

Every SCD (Type 1 / 2 / 7) and incremental-merge knot repeats the same
validation prologue at the top of ``process()``: confirm that pool
arguments really are :class:`DatabaseConnectionPool` instances, confirm
that free-text SQL fragments (raw queries, table names) are non-empty
strings, and confirm that column-name identifiers are safe to splice
into SQL. Several of them also repeat the same row-classification and
per-row upsert-execution steps once the validation has passed. This
base class centralises both kinds of repetition as ``@staticmethod``
helpers so each concrete knot's ``process()`` calls them instead of
duplicating the loop bodies.

SQL query builders remain private, per-subclass helpers (Rule 5 of
``docs/contributing/knot-design-rules.md``) — this base class has no
knowledge of any concrete knot's SQL shape; it only receives
already-built query strings and resolved values.

Algorithm:
    Validation helpers:

    1. ``_validate_pools`` accepts pool arguments by keyword (e.g.
       ``source_pool=...``, ``target_pool=...``) and raises ``TypeError``
       naming the first one that is not a ``DatabaseConnectionPool``,
       checking in the order the keywords were passed.
    2. ``_validate_non_empty_string`` raises ``ValueError`` when a
       caller-supplied string argument (a raw SQL query or a table name)
       is not a non-empty ``str``.
    3. ``_validate_identifier`` validates a single column/table
       identifier when given a ``str``, or a whole sequence of column
       identifiers when given a ``Sequence[str]``, delegating to
       :class:`~pirn_data.identifier_validator.IdentifierValidator` in
       either case.

    Merge helpers (shared by the bulk-classify SCD Type 1/2/7 knots):

    4. ``_index_rows_by_key`` builds a ``{key_tuple: row_tuple}`` lookup
       from a sequence of rows, given the positional indices that make
       up the key.
    5. ``_validate_row_width`` raises ``ValueError`` when a materialised
       row's width does not match the caller's declared column count.
    6. ``_non_key_values_changed`` compares the non-key values of an
       existing row against a candidate row and reports whether they
       differ.

    Merge helper (shared by the per-row upsert knots):

    7. ``_execute_per_row_upsert`` issues one SELECT-then-UPDATE-or-INSERT
       cycle per source row and returns, per row, whether it matched an
       existing key (``True``) or was inserted (``False``), so callers
       can tally the outcome under whatever field names their summary
       dict uses.

References:
    [1] docs/contributing/knot-remediation-process.md — extracting
        repeated validation and merge logic into private static helpers.
    [2] pirn_data/identifier_validator.py — the underlying identifier
        safety checks this class delegates to.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot

from pirn_data.identifier_validator import IdentifierValidator


class _PoolMergeKnot(Knot):
    """Shared static validation helpers for pool-backed merge/SCD knots."""

    @staticmethod
    def _validate_pools(knot_name: str, **pools: Any) -> None:
        """Raise ``TypeError`` naming the first keyword that is not a pool.

        ``pools`` maps each pool parameter's name (``"source_pool"``,
        ``"target_pool"``) to its resolved value, e.g.::

            _PoolMergeKnot._validate_pools(
                "ScdType1", source_pool=source_pool, target_pool=target_pool
            )
        """
        for pool_name, pool_value in pools.items():
            if not isinstance(pool_value, DatabaseConnectionPool):
                raise TypeError(f"{knot_name}: {pool_name} must be a DatabaseConnectionPool")

    @staticmethod
    def _validate_non_empty_string(knot_name: str, label: str, value: Any) -> None:
        """Raise ``ValueError`` if ``value`` is not a non-empty ``str``."""
        if not isinstance(value, str) or not value:
            raise ValueError(f"{knot_name}: {label} must be a non-empty string")

    @staticmethod
    def _validate_identifier(label: str, value: str | Sequence[str]) -> None:
        """Validate one identifier, or a sequence of identifiers.

        A ``str`` value (e.g. a table name) is validated as a single
        column-shaped identifier. Anything else is treated as a sequence
        of column names and validated element-wise. Both forms delegate
        to :class:`IdentifierValidator`, so error messages and exception
        types are unchanged from calling it directly.
        """
        if isinstance(value, str):
            IdentifierValidator.validate_column(label, value)
        else:
            IdentifierValidator.validate_columns(label, value)

    @staticmethod
    def _index_rows_by_key(
        rows: Sequence[Sequence[Any]], key_indices: tuple[int, ...]
    ) -> dict[tuple[Any, ...], tuple[Any, ...]]:
        """Index ``rows`` by the tuple of values at ``key_indices``.

        Later rows with a repeated key overwrite earlier ones, matching a
        plain dict-building loop over the source sequence.
        """
        existing_by_key: dict[tuple[Any, ...], tuple[Any, ...]] = {}
        for row in rows:
            row_t = tuple(row)
            key = tuple(row_t[i] for i in key_indices)
            existing_by_key[key] = row_t
        return existing_by_key

    @staticmethod
    def _validate_row_width(
        knot_name: str, row: Sequence[Any], column_tuple: tuple[str, ...]
    ) -> None:
        """Raise ``ValueError`` when ``row`` does not have one value per column."""
        if len(row) != len(column_tuple):
            raise ValueError(
                f"{knot_name}: row width {len(row)} does not match "
                f"column_names width {len(column_tuple)}"
            )

    @staticmethod
    def _non_key_values_changed(
        existing: tuple[Any, ...],
        row: tuple[Any, ...],
        non_key_indices: tuple[int, ...],
    ) -> bool:
        """Report whether ``row``'s non-key values differ from ``existing``'s."""
        return tuple(existing[i] for i in non_key_indices) != tuple(row[i] for i in non_key_indices)

    @staticmethod
    async def _execute_per_row_upsert(
        source_rows: Sequence[Sequence[Any]],
        target_pool: DatabaseConnectionPool,
        key_tuple: tuple[str, ...],
        non_key_tuple: tuple[str, ...],
        select_existing_query: str,
        update_query: str,
        insert_query: str,
    ) -> list[bool]:
        """Upsert each of ``source_rows`` individually against ``target_pool``.

        For every row, SELECT by key to decide whether it already exists,
        then UPDATE the non-key values or INSERT the full row accordingly.
        Returns one ``bool`` per input row — ``True`` when it matched an
        existing key (an UPDATE was issued), ``False`` when it was new (an
        INSERT was issued) — so callers can tally the outcome under
        whatever field names their own summary dict uses.
        """
        all_columns = key_tuple + non_key_tuple
        matched: list[bool] = []
        for row in source_rows:
            row_dict = dict(zip(all_columns, row, strict=False))
            key_values = tuple(row_dict[k] for k in key_tuple)
            non_key_values = tuple(row_dict[k] for k in non_key_tuple)
            existing = await target_pool.fetch_all(select_existing_query, key_values)
            if existing:
                await target_pool.execute(update_query, non_key_values + key_values)
                matched.append(True)
            else:
                await target_pool.execute(insert_query, key_values + non_key_values)
                matched.append(False)
        return matched
