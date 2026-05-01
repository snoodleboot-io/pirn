"""``SparkDataFrame`` — Tier-3 adapter wrapping a ``pyspark.sql.DataFrame``.

Spark DataFrames are lazy: ``filter``, ``groupBy``, ``join``, etc. all
extend the logical plan. Materialisation happens only when a terminal
sink (:class:`SparkCollectSink` or :class:`SparkWriteSink`) calls
``collect`` or ``write.save``. The wrapper carries the deferred frame
plus lineage metadata.

PySpark version constraint: ``pyspark>=4.0`` is required for Python 3.13+;
``pyspark>=3.5`` is acceptable on older Pythons. See ``pyproject.toml``
``[spark]`` extra.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


@dataclass(frozen=True)
class SparkDataFrame:
    """A ``pyspark.sql.DataFrame`` plus its provenance metadata.

    Attributes
    ----------
    frame:
        The deferred ``pyspark.sql.DataFrame``. Typed as ``Any`` to keep
        the ``pyspark`` import lazy (only required when constructed).
        Pirn does not call ``collect`` / ``write`` on this object — that's
        the sink's job.
    backend_name:
        Human-readable backend identifier (typically ``"spark"``).
    source_uri:
        Optional path/URI hint for lineage. DSN-style values must be
        scrubbed before assignment.
    fetched_at:
        UTC instant the frame was constructed.
    """

    frame: Any
    backend_name: str = "spark"
    source_uri: str = ""
    fetched_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(self.frame.columns)

    def with_frame(self, frame: Any) -> "SparkDataFrame":
        """Return a copy with ``frame`` replaced; metadata preserved."""
        return SparkDataFrame(
            frame=frame,
            backend_name=self.backend_name,
            source_uri=self.source_uri,
            fetched_at=self.fetched_at,
        )

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        """Tell pydantic to treat this batch as opaque.

        Pirn IO validation only needs ``isinstance(value, SparkDataFrame)``;
        descending into the underlying Spark plan would force eager work.
        """
        return core_schema.is_instance_schema(cls)
