"""``MetadataCatalog`` capability — discover and describe entities.

For connectors that expose a metadata catalog (DataHub, OpenMetadata,
Alation, dbt artifacts). Callers iterate over entities of a given type
and can fetch full metadata for a specific entity id.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Mapping


class MetadataCatalog:
    """Capability for connectors that expose entity catalogs."""

    async def list_entities(
        self,
        entity_type: str,
        *,
        filter: Mapping[str, Any] | None = None,
    ) -> AsyncIterator[Mapping[str, Any]]:
        """Yield entities of ``entity_type`` matching ``filter``.

        ``entity_type`` is vendor-specific — e.g., ``"dataset"``,
        ``"dashboard"``, ``"glossaryTerm"``. Concrete implementations
        document the supported types.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must implement list_entities()"
        )

    async def describe_entity(
        self,
        entity_id: str,
    ) -> Mapping[str, Any]:
        """Return full metadata for one entity by id."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement describe_entity()"
        )
