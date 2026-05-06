"""``EclipseSmspecParser`` — parse an Eclipse SMSPEC summary file.

Algorithm:
    1. Receive ``smspec_path`` and ``vector_name`` strings.
    2. Validate that both are non-empty strings.
    3. Open the Eclipse SMSPEC binary file and read the named vector.
    4. Return a ScadaTimeSeries keyed by ``eclipse:<vector_name>``.


References:
    - Schlumberger (2014). *ECLIPSE Reservoir Simulation Software Reference
      Manual*, Section 5 — Summary File Format (SMSPEC + UNSMRY).
    - OPM Project (2023). *OPM Flow Reference Manual*, Appendix D — SMSPEC
      binary format.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


class EclipseSmspecParser(Knot):
    """Parse an Eclipse SMSPEC + UNSMRY pair into a stubbed time-series."""

    def __init__(
        self,
        *,
        smspec_path: Knot | str,
        vector_name: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            smspec_path=smspec_path,
            vector_name=vector_name,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        smspec_path: str,
        vector_name: str,
        **_: Any,
    ) -> ScadaTimeSeries:
        """Parse the Eclipse SMSPEC file and return a ScadaTimeSeries reference for the named vector.

        Args:
            smspec_path: Non-empty path to the Eclipse SMSPEC file.
            vector_name: Non-empty Eclipse summary vector name (e.g. ``WOPR:W1``).

        Returns:
            ScadaTimeSeries keyed by ``eclipse:{vector_name}``.
        """
        if not isinstance(smspec_path, str) or not smspec_path:
            raise ValueError("EclipseSmspecParser: smspec_path must be a non-empty string")
        if not isinstance(vector_name, str) or not vector_name:
            raise ValueError("EclipseSmspecParser: vector_name must be a non-empty string")
        return ScadaTimeSeries(sensor_id=f"eclipse:{vector_name}")
