"""``ElandDataFrame`` — Tier-4 adapter wrapping an ``eland.DataFrame``.

Eland is the Elasticsearch DataFrame API: a Pandas-shaped facade that
push-down-translates operations into Elasticsearch DSL queries, so
filtering / aggregation runs in the cluster rather than locally. This
adapter is the value flowing between Eland Tier-4 knots; materialise to
a real Pandas frame via :class:`ElandToPandas` (or call
``eland.eland_to_pandas`` directly) when the rows need to leave the
cluster.

Pirn's IO validation uses pydantic to check values flowing between
knots. ``eland.DataFrame`` is not pydantic-friendly, so we expose an
``is_instance`` core schema and let pydantic treat the wrapper as
opaque.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


@dataclass(frozen=True)
class ElandDataFrame:
    """A handle to an ``eland.DataFrame`` plus its provenance metadata.

    Attributes
    ----------
    frame:
        The underlying ``eland.DataFrame``. Treated as opaque by pirn —
        downstream knots call its native methods directly.
    source_uri:
        Where the data lives (Elasticsearch URL + index name).
    fetched_at:
        UTC instant the handle was opened.
    """

    frame: Any
    source_uri: str = ""
    fetched_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        """Tell pydantic to treat this handle as opaque.

        The wrapped ``eland.DataFrame`` is not pydantic-compatible; this
        override makes pydantic just check
        ``isinstance(value, ElandDataFrame)``.
        """
        return core_schema.is_instance_schema(cls)
