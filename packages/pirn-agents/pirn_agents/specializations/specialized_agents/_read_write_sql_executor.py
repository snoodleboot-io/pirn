"""``ReadWriteSQLExecutor`` — internal helper Knot for :class:`ReadWriteSQLAgent`.

The write-enabled sibling of
:class:`~pirn_agents.specializations.specialized_agents._sql_executor.SQLExecutor`.
It still runs the inline-interpolation guard on every statement; it only skips
the read-only guard, and executes on an acquired connection that commits or
rolls back exactly the transaction its own statement opened.

Writing is chosen by constructing this class rather than by a knot input, so no
upstream knot's output — on this pipeline, output derived from model text — can
ever flip it (PIR-817).

References:
    pirn-native — no external references.
"""

from __future__ import annotations

from typing import ClassVar

from pirn_agents.specializations.specialized_agents._sql_executor import SQLExecutor


class ReadWriteSQLExecutor(SQLExecutor):
    """Validate the SQL against the interpolation guard and run it, permitting writes."""

    _read_only: ClassVar[bool] = False
