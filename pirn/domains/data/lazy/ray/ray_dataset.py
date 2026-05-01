"""``RayDataset`` — Tier-3 adapter wrapping a ``ray.data.Dataset``.

Ray Data datasets are lazy: ``filter``, ``map_batches``, ``groupby``,
etc. all build up a deferred plan. Materialisation happens only when the
terminal sink (:class:`RayCompute`) calls ``ds.materialize()`` /
``ds.write_*`` / ``ds.take(...)``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import ray.data
from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


@dataclass(frozen=True)
class RayDataset:
    """A ``ray.data.Dataset`` plus its provenance metadata.

    Attributes
    ----------
    dataset:
        The deferred ``ray.data.Dataset``. Pirn does not call
        ``materialize()`` / ``take()`` on this object — that's the sink's
        job.
    backend_name:
        Human-readable backend identifier (typically ``"ray"``).
    source_uri:
        Optional path/URI hint for lineage.
    fetched_at:
        UTC instant the dataset was constructed.
    """

    dataset: ray.data.Dataset
    backend_name: str = "ray"
    source_uri: str = ""
    fetched_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def with_dataset(self, dataset: ray.data.Dataset) -> "RayDataset":
        """Return a copy with ``dataset`` replaced; metadata preserved."""
        return RayDataset(
            dataset=dataset,
            backend_name=self.backend_name,
            source_uri=self.source_uri,
            fetched_at=self.fetched_at,
        )

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        """Tell pydantic to treat this batch as opaque."""
        return core_schema.is_instance_schema(cls)
