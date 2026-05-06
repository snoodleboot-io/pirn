"""Interface for seismic-volume stores (SEG-Y archives, vendor APIs)."""

from __future__ import annotations

from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.domains.oilgas.types.segy_volume import SegyVolume


class SeismicVolumeStore(PirnOpaqueValue):
    """Interface every seismic-volume store implementation must satisfy.

    Concrete adapters (object-store buckets of SEG-Y files, vendor APIs)
    inherit and override every method.
    """

    async def fetch_volume(self, volume_id: str) -> SegyVolume:
        """Resolve ``volume_id`` to a :class:`SegyVolume` reference."""
        raise NotImplementedError(f"{type(self).__name__} must implement fetch_volume()")

    async def close(self) -> None:
        """Close the underlying transport and release resources."""
        raise NotImplementedError(f"{type(self).__name__} must implement close()")
