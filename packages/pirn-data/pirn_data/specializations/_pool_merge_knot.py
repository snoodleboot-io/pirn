"""``_PoolMergeKnot`` — shared validation helpers for pool-backed merge/SCD knots.

Every SCD (Type 1 / 2 / 7) and incremental-merge knot repeats the same
validation prologue at the top of ``process()``: confirm that pool
arguments really are :class:`DatabaseConnectionPool` instances, confirm
that free-text SQL fragments (raw queries, table names) are non-empty
strings, and confirm that column-name identifiers are safe to splice
into SQL. This base class centralises those three checks as
``@staticmethod`` helpers so each concrete knot's ``process()`` calls
them instead of repeating the ``isinstance``/``raise`` boilerplate.

SQL query builders remain private, per-subclass helpers (Rule 5 of
``docs/contributing/knot-design-rules.md``) — this base class has no
knowledge of any concrete knot's SQL shape and performs no I/O.

Algorithm:
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

References:
    [1] docs/contributing/knot-remediation-process.md — extracting
        repeated validation into private static helpers.
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
