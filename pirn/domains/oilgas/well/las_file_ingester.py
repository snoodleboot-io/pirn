"""``LasFileIngester`` — ingest a LAS log file into a :class:`LASFile` reference.

Production deployments parse via ``lasio``; this knot returns a typed
stub so the orchestration graph can be exercised without the heavy SDK
at unit-test time.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.las_file import LASFile


class LasFileIngester(Knot):
    """Resolve a LAS file path into a :class:`LASFile` reference."""

    def __init__(
        self,
        *,
        file_path: str,
        well_id: str,
        curves: Sequence[str],
        depth_unit: str = "m",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(file_path, str) or not file_path:
            raise ValueError(
                "LasFileIngester: file_path must be a non-empty string"
            )
        if not isinstance(well_id, str) or not well_id:
            raise ValueError(
                "LasFileIngester: well_id must be a non-empty string"
            )
        curve_tuple = tuple(curves)
        if not curve_tuple:
            raise ValueError("LasFileIngester: curves must be non-empty")
        for curve in curve_tuple:
            if not isinstance(curve, str) or not curve:
                raise ValueError(
                    "LasFileIngester: every curve name must be a non-empty string"
                )
        if depth_unit not in ("m", "ft"):
            raise ValueError(
                "LasFileIngester: depth_unit must be 'm' or 'ft'"
            )
        self._file_path = file_path
        self._well_id = well_id
        self._curves = curve_tuple
        self._depth_unit = depth_unit
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> LASFile:
        """Resolve the configured file path and well metadata into a LASFile reference.

        Returns:
            LASFile reference built from the configured well ID, curve list, and depth unit.
        """
        return LASFile(
            well_id=self._well_id,
            curves=self._curves,
            depth_unit=self._depth_unit,
        )
