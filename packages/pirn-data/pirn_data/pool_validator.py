"""Shared argument validation for every pool-backed knot in ``pirn-data``.

Every knot that drives a :class:`~pirn.connectors.database_connection_pool.DatabaseConnectionPool`
opens ``process()`` with the same prologue: confirm the pool arguments really
are pools, confirm the free-text SQL fragments (raw queries, table names) are
non-empty strings, and confirm the column identifiers are safe to splice into
SQL. That prologue was previously hand-written once per knot — 72 copies of
``if not isinstance(pool, DatabaseConnectionPool): raise TypeError(...)`` across
46 modules, each free to drift in wording, in which arguments it checked, and in
whether it checked at all. This class is the single implementation; every
pool-backed knot calls it.

It is a plain helper class rather than a knot base because the knots that need
it do not share a base: :class:`~pirn_data.sources.sql_source.SqlSource` is a
``Source``, the SCD merges extend
:class:`~pirn_data.specializations.pool_merge_knot.PoolMergeKnot`, and the rest
extend ``Knot`` directly. Validation is not a place in a hierarchy.

Algorithm:
    1. ``validate_pools`` walks the keyword arguments in the order given and
       raises ``TypeError`` naming the first that is not a
       ``DatabaseConnectionPool``.
    2. ``validate_optional_pools`` does the same but accepts ``None`` for an
       argument the knot treats as "not supplied".
    3. ``validate_non_empty_string`` raises ``ValueError`` when a
       caller-supplied string (a raw SQL query, a table name) is not a
       non-empty ``str``.
    4. ``validate_identifier`` validates a single identifier when given a
       ``str`` and a whole sequence of identifiers otherwise, delegating to
       :class:`~pirn_data.identifier_validator.IdentifierValidator`.

References:
    [1] pirn_data/identifier_validator.py — the identifier safety rules this
        class delegates to.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool

from pirn_data.identifier_validator import IdentifierValidator


class PoolValidator:
    """Validate the pool, string and identifier arguments of a pool-backed knot."""

    @staticmethod
    def validate_pools(knot_name: str, **pools: Any) -> None:
        """Raise ``TypeError`` naming the first keyword that is not a pool.

        ``pools`` maps each pool parameter's name (``"source_pool"``,
        ``"target_pool"``) to its resolved value, e.g.::

            PoolValidator.validate_pools(
                "ScdType1", source_pool=source_pool, target_pool=target_pool
            )

        Args:
            knot_name: The knot's class name, used to prefix the message.
            pools: Pool parameter name -> resolved value, checked in order.

        Raises:
            TypeError: If any value is not a ``DatabaseConnectionPool``.
        """
        for pool_name, pool_value in pools.items():
            if not isinstance(pool_value, DatabaseConnectionPool):
                raise TypeError(f"{knot_name}: {pool_name} must be a DatabaseConnectionPool")

    @staticmethod
    def validate_optional_pools(knot_name: str, **pools: Any) -> None:
        """Like :meth:`validate_pools`, but ``None`` is accepted for any argument.

        For a knot whose pool argument is genuinely optional — a dimension
        lookup that may reuse the fact pool, for instance. ``None`` means "not
        supplied"; anything else must still be a pool.

        Raises:
            TypeError: If a value is neither ``None`` nor a
                ``DatabaseConnectionPool``.
        """
        supplied = {name: value for name, value in pools.items() if value is not None}
        PoolValidator.validate_pools(knot_name, **supplied)

    @staticmethod
    def validate_non_empty_string(knot_name: str, label: str, value: Any) -> None:
        """Raise ``ValueError`` if ``value`` is not a non-empty ``str``.

        Raises:
            ValueError: If ``value`` is not a ``str``, or is the empty string.
        """
        if not isinstance(value, str) or not value:
            raise ValueError(f"{knot_name}: {label} must be a non-empty string")

    @staticmethod
    def validate_identifier(label: str, value: str | Sequence[str]) -> None:
        """Validate one identifier, or a sequence of identifiers.

        A ``str`` value (e.g. a table name) is validated as a single
        column-shaped identifier. Anything else is treated as a sequence of
        column names and validated element-wise. Both forms delegate to
        :class:`IdentifierValidator`, so error messages and exception types are
        unchanged from calling it directly.
        """
        if isinstance(value, str):
            IdentifierValidator.validate_column(label, value)
        else:
            IdentifierValidator.validate_columns(label, value)
