"""``DeviationSurveyPayload`` — deviation survey metadata bundled with station table.

``survey`` carries the lineage metadata (well_id, station_count).
``data`` is a float64 array of shape ``(N, 3)`` where columns are
measured depth (ft), inclination (degrees), and azimuth (degrees).
Both fields travel together so downstream trajectory knots receive the
full station table in one input.
"""

from __future__ import annotations

import numpy as np
from pirn.core.payload import Payload

from pirn_oilgas.types.deviation_survey import DeviationSurvey


class DeviationSurveyPayload(Payload[DeviationSurvey, np.ndarray]):
    """Directional survey: metadata + (N, 3) station array [md_ft, inc_deg, azi_deg]."""

    @property
    def survey(self) -> DeviationSurvey:
        return self._metadata

    @property
    def stations(self) -> np.ndarray:
        return self._data
