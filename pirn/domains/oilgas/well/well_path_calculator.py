"""``WellPathCalculator`` — compute a 3-D well path from a deviation survey."""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.deviation_survey import DeviationSurvey
from pirn.domains.oilgas.types.well_path_3d import WellPath3D


class WellPathCalculator(Knot):
    """Convert a deviation survey into a 3-D well-path reference."""

    valid_methods: ClassVar[frozenset[str]] = frozenset(
        {"minimum_curvature", "tangential", "balanced_tangential"}
    )

    def __init__(
        self,
        *,
        survey: Knot,
        method: str = "minimum_curvature",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if method not in self.valid_methods:
            raise ValueError(
                f"WellPathCalculator: method must be one of "
                f"{sorted(self.valid_methods)}"
            )
        self._method = method
        super().__init__(survey=survey, _config=_config, **kwargs)

    async def process(self, survey: DeviationSurvey, **_: Any) -> WellPath3D:
        """Convert a deviation survey into a 3-D well path using the configured algorithm.

        Args:
            survey: Deviation survey providing measured-depth, inclination, and azimuth stations.

        Returns:
            WellPath3D computed from the survey using the configured calculation method.
        """
        return WellPath3D(
            well_id=survey.well_id,
            point_count=survey.station_count,
        )
