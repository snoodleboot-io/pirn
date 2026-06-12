"""``IbisTable`` — Tier-3 adapter wrapping an ``ibis.Table`` expression.

A Tier-3 knot's output is a *deferred* expression — no rows have been
materialised. Each downstream knot extends the expression. Execution
happens only when an :class:`IbisToTable` (or other terminal sink) calls
``.execute()`` / ``.to_table()``, at which point Ibis compiles the full
expression to one SQL query (or one Spark/Polars/… plan) and ships it to
the engine.

This is what "push-down" means in concrete terms: the data never enters
the Python process between tier-3 knots.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import ibis
from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


@dataclass(frozen=True)
class IbisTable:
    """An ``ibis.Table`` expression plus its provenance metadata.

    Attributes
    ----------
    expression:
        The deferred ``ibis.Table``. Pirn does not call ``.execute()``
        on this object — that's the sink's job. Treat as opaque between
        knots.
    backend_name:
        Human-readable backend identifier (e.g. ``"duckdb"``,
        ``"sqlite"``, ``"snowflake"``). Used in audit logs.
    source_uri:
        Optional connection-string hint for lineage. DSN-style values
        must be passed through
        :class:`pirn.connectors.dsn_scrubber.DsnScrubber` before
        assignment.
    fetched_at:
        UTC instant the expression was constructed.
    """

    expression: ibis.Table
    backend_name: str = ""
    source_uri: str = ""
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def schema(self) -> Any:
        """Return the Ibis schema of the deferred expression."""
        return self.expression.schema()

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(self.expression.columns)

    def with_expression(self, expression: ibis.Table) -> IbisTable:
        """Return a copy with ``expression`` replaced; metadata preserved."""
        return IbisTable(
            expression=expression,
            backend_name=self.backend_name,
            source_uri=self.source_uri,
            fetched_at=self.fetched_at,
        )

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        """Tell pydantic to treat this batch as opaque.

        Same rationale as
        :class:`pirn.domains.data.frames.polars.polars_data_batch.PolarsDataBatch`:
        the wrapped engine type isn't pydantic-compatible, so pirn IO
        validation just checks ``isinstance(value, IbisTable)``.
        """
        return core_schema.is_instance_schema(cls)
