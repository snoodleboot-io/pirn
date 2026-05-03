"""``MigrationProcessor`` — pre- or post-stack migration of a seismic volume."""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.segy_volume import SegyVolume


class MigrationProcessor(Knot):
    """Migrate a seismic volume using one of the supported algorithms."""

    valid_methods: ClassVar[frozenset[str]] = frozenset(
        {"kirchhoff", "rtm", "phase_shift", "stolt"}
    )

    def __init__(
        self,
        *,
        volume: Knot,
        method: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if method not in self.valid_methods:
            raise ValueError(
                f"MigrationProcessor: method must be one of "
                f"{sorted(self.valid_methods)}"
            )
        self._method = method
        super().__init__(volume=volume, _config=_config, **kwargs)

    @property
    def method(self) -> str:
        return self._method

    async def process(self, volume: SegyVolume, **_: Any) -> SegyVolume:
        """Migrate the input seismic volume using the configured algorithm and return the migrated SegyVolume.

        Args:
            volume: Pre-stack or post-stack seismic volume to migrate.

        Returns:
            SegyVolume of the migrated image.
        """
        return SegyVolume(volume_id=f"{volume.volume_id}:migrated_{self._method}")
