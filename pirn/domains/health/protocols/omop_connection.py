"""Interface for OMOP-CDM database connections.

Thin wrapper around a :class:`DatabaseConnectionPool` that exposes
OMOP-aware concept lookups. Concrete implementations resolve concept
ids against the OMOP vocabulary tables.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)


class OMOPConnection(PirnOpaqueValue):
    """Interface every OMOP-CDM connection must satisfy."""

    def __init__(self, pool: DatabaseConnectionPool | None = None) -> None:
        self._pool = pool

    @property
    def pool(self) -> DatabaseConnectionPool | None:
        return self._pool

    async def query_concept(self, concept_id: int) -> Mapping[str, Any]:
        """Return the OMOP concept row for ``concept_id``."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement query_concept()"
        )

    async def close(self) -> None:
        """Release the underlying pool."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement close()"
        )
