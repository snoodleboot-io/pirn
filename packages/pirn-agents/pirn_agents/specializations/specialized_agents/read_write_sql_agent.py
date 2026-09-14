"""``ReadWriteSQLAgent`` — :class:`SQLAgent` whose generated statement may write.

Identical to :class:`~pirn_agents.specializations.specialized_agents.sql_agent.SQLAgent`
except that the generated statement runs through
:class:`~pirn_agents.specializations.specialized_agents.read_write_sql_executor.ReadWriteSQLExecutor`:
the read-only guard is skipped, the inline-interpolation guard still applies,
and a write commits exactly the transaction it opened.

The statement is model-written, so writing is opt-in and explicit — chosen by
constructing this class, which no upstream knot's output can change (PIR-817).
Use it only where the agent is genuinely meant to write, and pair it with a
least-privilege database role.

Algorithm:
    Same as :class:`SQLAgent`, with the executor stage permitting writes.

References:
    pirn-native — no external references.
"""

from __future__ import annotations

from typing import ClassVar

from pirn_agents.specializations.specialized_agents.read_write_sql_executor import (
    ReadWriteSQLExecutor,
)
from pirn_agents.specializations.specialized_agents.sql_agent import SQLAgent
from pirn_agents.specializations.specialized_agents.sql_executor import SQLExecutor


class ReadWriteSQLAgent(SQLAgent):
    """Translate natural language to SQL and execute it, permitting writes."""

    _executor_class: ClassVar[type[SQLExecutor]] = ReadWriteSQLExecutor
