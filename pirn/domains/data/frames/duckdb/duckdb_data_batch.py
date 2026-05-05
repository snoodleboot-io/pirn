"""``DuckdbDataBatch`` — Tier-2 adapter wrapping a
:class:`duckdb.DuckDBPyRelation`.

DuckDB plays a slightly different role than Polars at Tier-2: it is an
in-process columnar SQL engine, and a ``DuckDBPyRelation`` is a
*deferred* relation (similar to Ibis but in-process). The relation
records the planned query — materialisation only happens when something
calls ``.df()``, ``.fetchall()``, ``.to_arrow()``, etc.

The adapter therefore holds three things together:

* the ``relation`` (planned query),
* the ``connection`` it was built against (necessary to run further SQL
  against the same in-process database),
* the standard provenance metadata (``source_uri``, ``fetched_at``).

Replace the relation via :meth:`with_relation` to keep instances
immutable. The connection is treated as part of the batch's identity —
all derived relations stay on the same connection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import duckdb
from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


@dataclass(frozen=True)
class DuckdbDataBatch:
    """A DuckDB relation plus its connection and provenance metadata.

    Attributes
    ----------
    relation:
        The deferred ``duckdb.DuckDBPyRelation``. Replace via
        :meth:`with_relation` to keep instances immutable.
    connection:
        The ``duckdb.DuckDBPyConnection`` the relation was built against.
        Carried alongside so downstream knots can issue further SQL on
        the same in-process database.
    source_uri:
        Where the data came from (DSN, file path, API endpoint). DSN-style
        values must be passed through
        :class:`pirn.domains.connectors.dsn_scrubber.DsnScrubber` before
        assignment.
    fetched_at:
        UTC instant the relation was constructed.
    """

    relation: duckdb.DuckDBPyRelation
    connection: duckdb.DuckDBPyConnection
    source_uri: str = ""
    fetched_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(self.relation.columns)

    def with_relation(
        self, relation: duckdb.DuckDBPyRelation
    ) -> DuckdbDataBatch:
        """Return a copy with ``relation`` replaced; everything else preserved."""
        return DuckdbDataBatch(
            relation=relation,
            connection=self.connection,
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
        dataclass fields and chokes on :class:`duckdb.DuckDBPyRelation`,
        which is not pydantic-compatible. Override here so pydantic just
        checks ``isinstance(value, DuckdbDataBatch)`` and leaves the
        wrapped relation alone.
        """
        return core_schema.is_instance_schema(cls)
