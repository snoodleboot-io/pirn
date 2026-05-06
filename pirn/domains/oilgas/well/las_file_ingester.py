"""``LasFileIngester`` — ingest a LAS log file into a :class:`LASFile` reference.

Production deployments parse via ``lasio``; this knot returns a typed
stub so the orchestration graph can be exercised without the heavy SDK
at unit-test time.

Algorithm:
    1. Receive a non-empty ``file_path``, a non-empty ``well_id``, a
       non-empty ``curves`` sequence, and an optional ``depth_unit``
       (``'m'`` or ``'ft'``).
    2. Validate all inputs.
    3. Open the LAS file and read well-information and curve-data sections.
    4. Return a LASFile reference with the configured metadata.


References:
    - LAS 2.0 File Format Standard (1992), Canadian Well Logging Society
      (file structure and section definitions).
    - LAS 3.0 File Format Standard (2001), Canadian Well Logging Society
      (extended parameter sections).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.las_file import LASFile


class LasFileIngester(Knot):
    """Resolve a LAS file path into a :class:`LASFile` reference."""

    def __init__(
        self,
        *,
        file_path: Knot | str,
        well_id: Knot | str,
        curves: Knot | Sequence[str],
        depth_unit: Knot | str = "m",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            file_path=file_path,
            well_id=well_id,
            curves=curves,
            depth_unit=depth_unit,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        file_path: str,
        well_id: str,
        curves: Sequence[str],
        depth_unit: str = "m",
        **_: Any,
    ) -> LASFile:
        """Resolve the configured file path and well metadata into a LASFile reference.

        Args:
            file_path: Non-empty path to the LAS file on disk.
            well_id: Non-empty well identifier string.
            curves: Non-empty sequence of curve mnemonic strings.
            depth_unit: Depth unit; must be ``'m'`` or ``'ft'`` (default ``'m'``).

        Returns:
            LASFile reference built from the configured well ID, curve list, and depth unit.
        """
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
        return LASFile(
            well_id=well_id,
            curves=curve_tuple,
            depth_unit=depth_unit,
        )
