"""``SparkExecutionReceipt`` — audit record returned by
:class:`pirn.domains.data.lazy.spark.spark_write_sink.SparkWriteSink` after a
deferred Spark plan has been materialised.

The receipt is treated as opaque to pydantic IO validation: a
``plain_serializer_function_ser_schema`` flattens it to a primitive dict
so downstream content addressing remains stable without round-tripping
through pydantic's dataclass machinery.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


@dataclass(frozen=True)
class SparkExecutionReceipt:
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
    completed_at: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        """Treat as opaque to pydantic; serialise to a primitive dict."""
        return core_schema.is_instance_schema(
            cls,
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda v: {
                    "succeeded": v.succeeded,
                    "row_count": v.row_count,
                    "output_path": v.output_path,
                    "completed_at": v.completed_at.isoformat(),
                },
                when_used="always",
            ),
        )
