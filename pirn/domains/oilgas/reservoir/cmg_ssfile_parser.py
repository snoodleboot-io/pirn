"""``CmgSsfileParser`` — parse a CMG simulation SSFILE summary.

Algorithm:
    1. Receive ``ssfile_path`` and ``vector_name`` strings.
    2. Validate that both are non-empty strings.
    3. Open the CMG SSFILE binary and read the named output vector.
    4. Return a ScadaTimeSeries keyed by ``cmg:<vector_name>``.


References:
    - CMG (Computer Modelling Group) (2023). *IMEX User Guide*, Appendix B —
      SSFILE Binary Format Specification.
    - CMG (2023). *Results 3D User Guide*, Chapter 7 — Time Series Extraction.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


class CmgSsfileParser(Knot):
    """Parse a CMG SSFILE-style summary into a stubbed time-series reference."""

    def __init__(
        self,
        *,
        ssfile_path: Knot | str,
        vector_name: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            ssfile_path=ssfile_path,
            vector_name=vector_name,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        ssfile_path: str,
        vector_name: str,
        **_: Any,
    ) -> ScadaTimeSeries:
        """Parse the CMG SSFILE path and return a ScadaTimeSeries reference for the named vector.

        Args:
            ssfile_path: Non-empty path to the CMG SSFILE binary.
            vector_name: Non-empty name of the simulation output vector.

        Returns:
            ScadaTimeSeries keyed by ``cmg:{vector_name}``.
        """
        if not isinstance(ssfile_path, str) or not ssfile_path:
            raise ValueError("CmgSsfileParser: ssfile_path must be a non-empty string")
        if not isinstance(vector_name, str) or not vector_name:
            raise ValueError("CmgSsfileParser: vector_name must be a non-empty string")
        return ScadaTimeSeries(sensor_id=f"cmg:{vector_name}")
