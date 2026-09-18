"""``PoolMergeKnot`` — shared row-classification helpers for pool-backed SCD merges.

The bulk-classify SCD merges (Type 1 / 2 / 7) all read the target table's
current rows, index them by natural key, and compare a candidate source row's
non-key values against the stored ones to decide INSERT / UPDATE / skip. This
base class owns those steps as ``@staticmethod`` helpers so each concrete knot's
``process()`` calls them instead of repeating the loop bodies.

Argument validation is **not** here: it lives in
:class:`~pirn_data.pool_validator.PoolValidator`, which every pool-backed knot
in the package uses whether or not it extends this class. A knot's place in a
hierarchy is not what decides whether its arguments are checked.

SQL query builders remain private, per-subclass helpers (Rule 5 of
``docs/contributing/knot-design-rules.md``) — this base class has no knowledge
of any concrete knot's SQL shape; it only receives already-built query strings
and resolved values.

Algorithm:
    1. ``_index_rows_by_key`` builds a ``{key_tuple: row_tuple}`` lookup from a
       sequence of rows, given the positional indices that make up the key.
    2. ``_validate_row_width`` raises ``ValueError`` when a materialised row's
       width does not match the caller's declared column count.
    3. ``_non_key_values_changed`` compares the non-key values of an existing
       row against a candidate row and reports whether they differ.

References:
    [1] docs/contributing/knot-remediation-process.md — extracting repeated
        merge logic into private static helpers.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot


class PoolMergeKnot(Knot):
    """Shared static row-classification helpers for the pool-backed SCD merges."""

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
