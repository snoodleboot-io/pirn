"""``DuckDBConnection`` — pydantic-opaque wrapper for :class:`duckdb.DuckDBPyConnection`.

:class:`duckdb.DuckDBPyConnection` is a C++-backed native object that pydantic
cannot introspect or serialise. This thin wrapper inherits
:class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue` so it receives an opaque
``isinstance`` schema, allowing it to travel between Knots in the pirn graph
without triggering pydantic schema generation errors.

The wrapped connection is accessed via the read-only :attr:`conn` property.
Analogous to :class:`~pirn.domains.data.frames.datafusion.datafusion_session_context.DatafusionSessionContext`.
"""

from __future__ import annotations

from typing import Any

import duckdb

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class DuckDBConnection(PirnOpaqueValue):
    """Pydantic-opaque holder for a :class:`duckdb.DuckDBPyConnection`.

    Pass this through the pirn graph and unwrap with ``.conn`` in any
    consuming Knot's ``process()`` method.
    """

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        return self._conn

    def _pirn_audit_dict(self) -> Any:
        return f"<DuckDBConnection@{id(self._conn):x}>"
