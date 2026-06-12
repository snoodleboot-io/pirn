"""``WellPath3DPayload`` — 3-D well path metadata bundled with coordinate array.

``path`` carries the lineage metadata (well_id, point_count).
``data`` is a float64 array of shape ``(N, 3)`` where columns are
northing (ft), easting (ft), and true vertical depth (ft).
Both fields travel together so downstream knots receive the full
coordinate buffer in one input.
"""

from __future__ import annotations

import numpy as np

from pirn.core.payload import Payload
from pirn.domains.oilgas.types.well_path_3d import WellPath3D


class WellPath3DPayload(Payload[WellPath3D, np.ndarray]):
    """3-D well path: metadata + (N, 3) coordinate array [northing_ft, easting_ft, tvd_ft]."""

    @property
    def path(self) -> WellPath3D:
        return self._metadata

    @property
    def points(self) -> np.ndarray:
        return self._data
