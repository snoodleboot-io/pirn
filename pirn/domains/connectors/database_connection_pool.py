"""Interface for async database connection pools.

Concrete implementations (asyncpg, aiosqlite, DuckDB, ...) inherit from
:class:`DatabaseConnectionPool` and override every method. Following the
existing pirn interface convention (see ``pirn/streaming/base.py``,
``pirn/triggers/base.py``, ``pirn/backends/base/run_history.py``) — base
methods raise :class:`NotImplementedError` naming the concrete subclass
that failed to implement them.
"""

from __future__ import annotations

import re
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class DatabaseConnectionPool(PirnOpaqueValue):
    """Interface every connector pool implementation must satisfy.

    Implementations:
      - :class:`pirn.domains.connectors.databases.sqlite_pool.SqlitePool`
      - :class:`pirn.domains.connectors.databases.duckdb_pool.DuckdbPool`
      - :class:`pirn.domains.connectors.databases.postgres_pool.PostgresPool`

    Pydantic treats pools as opaque (see
    :class:`pirn.core.pirn_opaque_value.PirnOpaqueValue`); the default
    identity-keyed serialiser keeps content-addressing cache stable
    without descending into live engine state.
    """

    async def acquire(self) -> Any:
        """Return a connection (or async-context manager wrapping one)."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement acquire()"
        )

    async def release(self, connection: Any) -> None:
        """Return a previously-acquired connection to the pool."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement release()"
        )

    async def close(self) -> None:
        """Close the pool and release any underlying resources."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement close()"
        )

    # Per-engine placeholder grammar. The default regex rejects Python
    # brace interpolation (``{...}``) and printf-style (``%s``/``%d``).
    # Subclasses override ``_inline_interpolation_pattern`` when their
    # driver uses one of those forms as a real bind marker:
    #
    # * MySQL  — uses ``%s`` as the canonical placeholder.
    # * Clickhouse — uses ``{name:Type}`` as a typed placeholder.
    _inline_interpolation_pattern: str = r"\{[^}]*\}|%[sd]"

    def _reraise_scrubbed(self, exc: BaseException) -> None:
        """Re-raise ``exc`` with credential markers scrubbed from the message.

        Concrete pools construct ``self._scrubber`` (a
        :class:`pirn.domains.connectors.dsn_scrubber.DsnScrubber`) in their
        ``__init__``. This helper centralises the
        ``raise type(exc)(scrubber.scrub(str(exc))) from None`` pattern so
        every concrete pool's connect/auth ``except`` block stays a single
        line.
        """
        raise type(exc)(self._scrubber.scrub(str(exc))) from None

    def _reject_inline_interpolation(self, query: str) -> None:
        """Reject Python-string interpolation markers in raw SQL.

        Defends against accidental use of ``str.format`` (``{...}``) or
        printf-style (``%s``/``%d``) substitution in places where the
        caller should be using the driver's bind syntax. Every concrete
        pool calls this from its query-executing methods *before*
        forwarding to the underlying driver.
        """
        if re.search(self._inline_interpolation_pattern, query):
            hint = (
                "Use the driver's bind syntax (':name', '?', or '%s' "
                "depending on the engine) and pass parameters separately."
            )
            raise ValueError(
                f"{type(self).__name__}: query contains inline interpolation "
                f"markers. {hint}"
            )

