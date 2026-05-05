"""``RayExecutionReceipt`` — audit record returned by
:class:`pirn.domains.data.lazy.ray.ray_compute.RayCompute` after the
deferred Ray Data plan has been materialised.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class RayExecutionReceipt:
    """Lineage-friendly summary of one Tier-3 Ray execution.

    Attributes
    ----------
    backend_name:
        Engine the plan ran on (typically ``"ray"``).
    target_path:
        Destination URI/path when the sink wrote results back; ``None``
        when the sink only materialised in-memory.
    dataset_size:
        ``ds.count()`` after materialisation, or ``None`` when the sink
        did not request a count (e.g. it only wrote out and skipped the
        extra scan).
    block_count:
        Number of blocks in the materialised dataset, or ``None`` if not
        available from the backend.
    executed_at:
        UTC instant of execution.
    """

    backend_name: str
    target_path: str | None
    dataset_size: int | None = None
    block_count: int | None = None
    executed_at: datetime = datetime(1970, 1, 1, tzinfo=UTC)
