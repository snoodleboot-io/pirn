"""``DatafusionDataBatch`` — Tier-2 adapter wrapping a
:class:`datafusion.DataFrame`.

DataFusion plays a similar role to DuckDB at Tier-2: it is an in-process
columnar SQL engine, and a ``datafusion.DataFrame`` is a *lazy* logical
plan. Materialisation only happens when something calls ``.collect()``,
``.to_pylist()``, ``.to_arrow_table()``, etc.

The adapter therefore holds three things together:

* the ``frame`` (lazy DataFrame),
* the ``context`` it was built against (necessary to register further
  tables/views and run additional SQL on the same engine state),
* the standard provenance metadata (``source_uri``, ``fetched_at``).

Replace the frame via :meth:`with_frame` to keep instances immutable.
The context is treated as part of the batch's identity — all derived
frames stay on the same context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import datafusion as df
from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


@dataclass(frozen=True)
class DatafusionDataBatch:
    """A DataFusion DataFrame plus its context and provenance metadata.

    Attributes
    ----------
    frame:
        The lazy ``datafusion.DataFrame``. Replace via :meth:`with_frame`
        to keep instances immutable.
    context:
        The ``datafusion.SessionContext`` the frame was built against.
        Carried alongside so downstream knots can register additional
        views or run SQL on the same in-process engine.
    source_uri:
        Where the data came from (DSN, file path, API endpoint). DSN-style
        values must be passed through
        :class:`pirn.domains.connectors.dsn_scrubber.DsnScrubber` before
        assignment.
    fetched_at:
        UTC instant the frame was constructed.
    """

    frame: df.DataFrame
    context: df.SessionContext
    source_uri: str = ""
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(self.frame.schema().names)

    def with_frame(self, frame: df.DataFrame) -> DatafusionDataBatch:
        """Return a copy with ``frame`` replaced; everything else preserved."""
        return DatafusionDataBatch(
            frame=frame,
            context=self.context,
            source_uri=self.source_uri,
            fetched_at=self.fetched_at,
        )

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        """Tell pydantic to treat this batch as opaque.

        Pirn's IO validation uses pydantic to check values flowing
        between knots. The default schema generator descends into
        dataclass fields and chokes on :class:`datafusion.DataFrame`,
        which is not pydantic-compatible. Override here so pydantic
        just checks ``isinstance(value, DatafusionDataBatch)`` and
        leaves the wrapped frame alone.
        """
        return core_schema.is_instance_schema(cls)
