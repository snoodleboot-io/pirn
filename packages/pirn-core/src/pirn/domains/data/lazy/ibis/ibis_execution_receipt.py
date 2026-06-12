"""``IbisExecutionReceipt`` — audit record returned by
:class:`pirn.domains.data.lazy.ibis.ibis_to_table.IbisToTable` after the
deferred expression has been compiled and executed.

The receipt is the *only* representation of a Tier-3 pipeline's result
that travels back into the Python process by default. Pirn captures it
in lineage so users can see what SQL ran, on which backend, where the
output landed, and how many rows were produced — without ever
materialising the rows themselves.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class IbisExecutionReceipt:
    """Lineage-friendly summary of one Tier-3 execution.

    Attributes
    ----------
    backend_name:
        Engine the query ran on (``"duckdb"``, ``"sqlite"``, …).
    target_table:
        Destination table when the sink wrote results back to the
        backend; ``None`` when the sink simply triggered compile + execute.
    compiled_sql:
        The query the backend ran. Useful for audit logs; truncated by
        callers if the SQL might be large.
    row_count:
        Rows in the result, or ``None`` when the backend doesn't expose
        a ``len`` on the executed value.
    executed_at:
        UTC instant of execution.
    """

    backend_name: str
    target_table: str | None
    compiled_sql: str
    row_count: int | None = None
    executed_at: datetime = datetime(1970, 1, 1, tzinfo=UTC)
