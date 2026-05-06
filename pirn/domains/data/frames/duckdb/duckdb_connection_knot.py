"""``DuckDBConnectionKnot`` — vending Knot for :class:`duckdb.DuckDBPyConnection`.

A DuckDB in-memory connection is a live native object that cannot travel
through the pirn graph (holds a C++ extension handle, not serialisable).
This vending Knot constructs one during ``process()`` and returns it so that
consumer Knots (bridges, transforms) can declare it as a typed upstream
dependency and receive the resolved connection in their own ``process()`` calls.

Share a single :class:`DuckDBConnectionKnot` across all Knots that need to
operate on the same in-process DuckDB database.

Algorithm:
    1. Open an in-memory DuckDB connection via ``duckdb.connect(":memory:")``.
    2. Return the connection so downstream Knots receive it as a resolved value.

References:
    [1] DuckDB Python API — duckdb.connect:
        https://duckdb.org/docs/api/python/overview.html
"""

from __future__ import annotations

from typing import Any

import duckdb

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.duckdb.duckdb_connection import DuckDBConnection


class DuckDBConnectionKnot(Knot):
    """Construct and vend a DuckDB in-memory connection.

    No inputs beyond ``_config`` — the connection is stateless at construction
    time. Downstream Knots declare this Knot as a typed ``__init__`` parameter
    and receive the :class:`DuckDBConnection` value in ``process()``.
    """

    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> DuckDBConnection:
        """Open and return a fresh DuckDB in-memory connection.

        Returns:
            A new :class:`DuckDBConnection` wrapping a ``duckdb.DuckDBPyConnection``
            connected to ``:memory:``.
        """
        return DuckDBConnection(duckdb.connect(database=":memory:"))
