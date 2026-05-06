"""``LanceDataset`` — Tier-4 adapter wrapping a ``lance.LanceDataset``.

Lance is a columnar format optimised for ML / realtime workloads. This
adapter is the value that flows between Lance Tier-4 knots; downstream
bridges can convert it to a ``pyarrow.Table`` (and from there to Polars,
Pandas, or DuckDB Tier-2 frames) when materialisation is needed.

Pirn's IO validation uses pydantic to check values flowing between
knots. ``lance.LanceDataset`` is not pydantic-friendly, so we expose an
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
class LanceDataset:
    """A handle to a ``lance.LanceDataset`` plus its provenance metadata.

    Attributes
    ----------
    dataset:
        The underlying ``lance.LanceDataset``. Treated as opaque by
        pirn — bridges and adapters call its native methods directly.
    source_uri:
        Where the dataset lives (filesystem path or ``s3://...``).
    fetched_at:
        UTC instant the handle was opened.
    """

    dataset: Any
    source_uri: str = ""
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        """Tell pydantic to treat this handle as opaque.

        The wrapped ``lance.LanceDataset`` is not pydantic-compatible;
        this override makes pydantic just check
        ``isinstance(value, LanceDataset)``.
        """
        return core_schema.is_instance_schema(cls)
