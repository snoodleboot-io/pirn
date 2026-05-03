"""``SegyFileIngester`` — ingest a SEG-Y file into a :class:`SegyVolume` reference.

Production deployments load real bytes through ``segyio``; this knot
returns a typed stub volume so the orchestration graph can be wired and
exercised without the heavyweight SDK at unit-test time.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.segy_volume import SegyVolume


class SegyFileIngester(Knot):
    """Resolve a SEG-Y file path into a :class:`SegyVolume` reference."""

    def __init__(
        self,
        *,
        file_path: str,
        volume_id: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(file_path, str) or not file_path:
            raise ValueError(
                "SegyFileIngester: file_path must be a non-empty string"
            )
        if not isinstance(volume_id, str) or not volume_id:
            raise ValueError(
                "SegyFileIngester: volume_id must be a non-empty string"
            )
        self._file_path = file_path
        self._volume_id = volume_id
        super().__init__(_config=_config, **kwargs)

    @property
    def file_path(self) -> str:
        return self._file_path

    @property
    def volume_id(self) -> str:
        return self._volume_id

    async def process(self, **_: Any) -> SegyVolume:
        """Resolve the configured SEG-Y file path and return a SegyVolume reference with the configured volume_id.

        Returns:
            SegyVolume reference identified by the configured volume ID.
        """
        return SegyVolume(volume_id=self._volume_id)
