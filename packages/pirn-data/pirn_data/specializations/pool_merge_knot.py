"""``PoolMergeKnot`` — shared source-resolution and row-classification for SCD merges.

The SCD merges (Type 1 / 2 / 7) all do the same three things before they differ:
take their source rows from either an upstream knot or a query they run against
a source pool, read the target table's current rows and index them by natural
key, then compare a candidate row's non-key values against the stored ones to
decide INSERT / UPDATE / EXPIRE / skip. This base class owns those steps so each
concrete knot's ``process()`` calls them instead of repeating the loop bodies.

Argument validation is **not** here: it lives in
:class:`~pirn_data.pool_validator.PoolValidator`, which every pool-backed knot
in the package uses whether or not it extends this class. A knot's place in a
hierarchy is not what decides whether its arguments are checked.

SQL query builders remain private, per-subclass helpers (Rule 5 of
``docs/contributing/knot-design-rules.md``) — this base class has no knowledge
of any concrete knot's SQL shape; it only receives already-built query strings
and resolved values.

Algorithm:
    1. ``_resolve_source_rows`` takes the two mutually-exclusive ways a merge
       receives rows — ``rows`` from an upstream knot, or ``source_query``
       against ``source_pool`` — insists on exactly one, and returns the
       materialised rows as tuples with each row's width checked against the
       declared ``column_names``.
    2. ``_index_rows_by_key`` builds a ``{key_tuple: row_tuple}`` lookup from a
       sequence of rows, given the positional indices that make up the key.
    3. ``_validate_row_width`` raises ``ValueError`` when a materialised row's
       width does not match the caller's declared column count.
    4. ``_non_key_values_changed`` compares the non-key values of an existing
       row against a candidate row and reports whether they differ.

References:
    [1] docs/contributing/knot-remediation-process.md — extracting repeated
        merge logic into private static helpers.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot

from pirn_data.pool_validator import PoolValidator


class PoolMergeKnot(Knot):
    """Shared static source-resolution and row-classification for the SCD merges."""

    @staticmethod
    async def _resolve_source_rows(
        knot_name: str,
        rows: Any,
        source_pool: Any,
        source_query: Any,
        column_tuple: tuple[str, ...],
    ) -> list[tuple[Any, ...]]:
        """Materialise the merge's source rows from exactly one of the two inputs.

        A merge is fed either by an upstream knot (``rows``) or by a query it
        runs itself (``source_pool`` + ``source_query``). Supplying both is
        ambiguous and supplying neither leaves nothing to merge, so both are
        refused rather than silently resolved.

        Args:
            knot_name: The knot's class name, used to prefix error messages.
            rows: Rows from an upstream knot, or ``None``.
            source_pool: Pool to run ``source_query`` against, or ``None``.
            source_query: SQL producing the source rows, or ``None``.
            column_tuple: The declared column names each row must match.

        Returns:
            The source rows as tuples, one value per declared column.

        Raises:
            ValueError: If neither or both row sources are supplied, if
                ``source_query`` is not a non-empty string, or if a row's width
                does not match ``column_tuple``.
            TypeError: If ``source_pool`` is supplied but is not a pool.
        """
        from_query = source_pool is not None or source_query is not None
        if rows is not None and from_query:
            raise ValueError(
                f"{knot_name}: supply either rows or source_pool+source_query, not both"
            )
        if rows is None and not from_query:
            raise ValueError(f"{knot_name}: supply either rows or source_pool+source_query")
        if rows is None:
            pool = PoolValidator.validate_pool(knot_name, "source_pool", source_pool)
            query = PoolValidator.validate_non_empty_string(knot_name, "source_query", source_query)
            rows = await pool.fetch_all(query)
        materialised: list[tuple[Any, ...]] = []
        for row in rows:
            row_t = tuple(row)
            PoolMergeKnot._validate_row_width(knot_name, row_t, column_tuple)
            materialised.append(row_t)
        return materialised

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
