"""``SparkExecutionReceipt`` — audit record returned by
:class:`pirn_data.lazy.spark.spark_write_sink.SparkWriteSink` after a
deferred Spark plan has been materialised.

The receipt is treated as opaque to pydantic IO validation: a
``plain_serializer_function_ser_schema`` flattens it to a primitive dict
so downstream content addressing remains stable without round-tripping
through pydantic's dataclass machinery.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class SparkExecutionReceipt(PirnOpaqueValue):
    """Lineage-friendly summary of one Tier-3 Spark execution.

    Attributes
    ----------
    succeeded:
        ``True`` if the deferred plan completed without raising.
    row_count:
        Rows in the materialised result, or ``None`` when the sink wrote
        out and didn't request a count.
    output_path:
        Destination URI/path when the sink wrote results back; ``None``
        when the sink only collected in-memory.
    completed_at:
        UTC instant of completion.
    """

    succeeded: bool
    row_count: int | None
    output_path: str | None
    completed_at: datetime = datetime(1970, 1, 1, tzinfo=UTC)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Flatten to a primitive dict for pydantic serialisation."""
        return {
            "succeeded": self.succeeded,
            "row_count": self.row_count,
            "output_path": self.output_path,
            "completed_at": self.completed_at.isoformat(),
        }
