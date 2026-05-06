"""Interface for well-master data services (well headers, lists)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class WellDataService(PirnOpaqueValue):
    """Interface every well-master data service implementation must satisfy."""

    async def fetch_well(self, well_id: str) -> Mapping[str, object]:
        """Return the master record for ``well_id``."""
        raise NotImplementedError(f"{type(self).__name__} must implement fetch_well()")

    async def list_wells(self, field_id: str) -> AsyncIterator[str]:
        """Yield ``well_id`` strings for every well in ``field_id``."""
        raise NotImplementedError(f"{type(self).__name__} must implement list_wells()")

    async def close(self) -> None:
        """Close the underlying transport and release resources."""
        raise NotImplementedError(f"{type(self).__name__} must implement close()")
