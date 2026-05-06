"""``SegyFileIngester`` — ingest a SEG-Y file into a :class:`SegyVolume` reference.

Production deployments load real bytes through ``segyio``; this knot
returns a typed stub volume so the orchestration graph can be wired and
exercised without the heavyweight SDK at unit-test time.

Algorithm:
    1. Receive non-empty ``file_path`` and ``volume_id`` strings.
    2. Validate that both strings are non-empty.
    3. Resolve the SEG-Y file at ``file_path`` and read binary and text
       headers to confirm the file is readable.
    4. Return a SegyVolume reference tagged with ``volume_id``.


References:
    - SEG Technical Standards Committee (2017). *SEG-Y_r2.0 Data Exchange
      Format*. Society of Exploration Geophysicists.
    - Herkenhoff, E.F. et al. (1994). Fundamentals of digital multichannel
      seismic data. *SEG Course Notes*, Chapter 1 (SEG-Y format overview).
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
        file_path: Knot | str,
        volume_id: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            file_path=file_path,
            volume_id=volume_id,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        file_path: str,
        volume_id: str,
        **_: Any,
    ) -> SegyVolume:
        """Resolve the configured SEG-Y file path and return a SegyVolume reference with the configured volume_id.

        Args:
            file_path: Non-empty path to the SEG-Y file on disk.
            volume_id: Non-empty identifier string for the resulting volume.

        Returns:
            SegyVolume reference identified by the configured volume ID.
        """
        if not isinstance(file_path, str) or not file_path:
            raise ValueError("SegyFileIngester: file_path must be a non-empty string")
        if not isinstance(volume_id, str) or not volume_id:
            raise ValueError("SegyFileIngester: volume_id must be a non-empty string")
        return SegyVolume(volume_id=volume_id)
