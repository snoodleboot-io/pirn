"""``DaskExecutionReceipt`` — audit record returned by
:class:`pirn.domains.data.lazy.dask.dask_compute.DaskCompute` after the
deferred Dask graph has been computed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class DaskExecutionReceipt:
    """Lineage-friendly summary of one Tier-3 Dask execution.

    Attributes
    ----------
    backend_name:
        Engine the graph ran on (typically ``"dask"``).
    target_path:
        Destination URI/path when the sink wrote results back; ``None``
        when the sink simply returned the materialised pandas DataFrame.
    partitions_executed:
        Number of partitions in the deferred frame at the time of
        execution.
    row_count:
        Rows in the result, or ``None`` when the sink wrote results
        out and didn't materialise a row count.
    executed_at:
        UTC instant of execution.
    """

    backend_name: str
    target_path: str | None
    partitions_executed: int
    row_count: int | None = None
    executed_at: datetime = datetime(1970, 1, 1, tzinfo=UTC)
