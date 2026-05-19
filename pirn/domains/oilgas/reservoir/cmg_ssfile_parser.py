"""``CmgSsfileParser`` — parse a CMG simulation SSFILE summary.

Algorithm:
    1. Receive ``ssfile_path`` and ``vector_name`` strings.
    2. Validate that both are non-empty strings.
    3. Open the CMG SSFILE text output and scan for the column header line
       that begins with ``'TIME'``. Column names are whitespace-delimited.
    4. Locate the column index matching ``vector_name`` (case-insensitive).
    5. Count data rows to derive ``sample_count`` and estimate
       ``sample_interval_sec`` from the median TIME delta (days → seconds).
    6. Return a :class:`ScadaTimeSeries` keyed by ``cmg:<vector_name>``.

CMG SSFILE format:
    Plain-text tabular output produced by CMG IMEX/GEM/STARS.  A header
    block of ``*`` comment lines precedes a row of whitespace-separated
    column names (the first column is always ``TIME`` in days), followed by
    numeric data rows.

References:
    - CMG (Computer Modelling Group) (2023). *IMEX User Guide*, Appendix B —
      SSFILE Text Format Specification.
    - CMG (2023). *Results 3D User Guide*, Chapter 7 — Time Series Extraction.
"""

from __future__ import annotations

import os
import statistics
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


class CmgSsfileParser(Knot):
    """Parse a CMG SSFILE text summary into a :class:`ScadaTimeSeries` reference."""

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
        """Parse the CMG SSFILE and return a ScadaTimeSeries for the named vector.

        Args:
            ssfile_path: Non-empty path to the CMG SSFILE text output.
            vector_name: Non-empty name of the simulation output vector
                (e.g. ``OILRATSC``). Case-insensitive.

        Returns:
            ScadaTimeSeries keyed by ``cmg:{vector_name}``.

        Raises:
            ValueError: If ssfile_path or vector_name is empty.
            FileNotFoundError: If the SSFILE does not exist.
            KeyError: If vector_name is not found in the SSFILE columns.
        """
        if not isinstance(ssfile_path, str) or not ssfile_path:
            raise ValueError("CmgSsfileParser: ssfile_path must be a non-empty string")
        if not isinstance(vector_name, str) or not vector_name:
            raise ValueError("CmgSsfileParser: vector_name must be a non-empty string")

        if not os.path.isfile(ssfile_path):
            raise FileNotFoundError(f"CmgSsfileParser: SSFILE not found: {ssfile_path}")

        seconds_per_day = 86400.0
        headers: list[str] = []
        time_values: list[float] = []

        with open(ssfile_path) as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("*"):
                    continue
                parts = line.split()
                if not headers:
                    # First non-comment line is the column header row.
                    if parts[0].upper() == "TIME":
                        headers = [p.upper() for p in parts]
                        needle = vector_name.upper()
                        if needle not in headers:
                            raise KeyError(
                                f"CmgSsfileParser: vector '{vector_name}' not found; "
                                f"available: {headers[1:]}"
                            )
                    continue
                # Data row — collect TIME column values for interval estimation.
                try:
                    time_values.append(float(parts[0]))
                except (ValueError, IndexError):
                    continue

        sample_count = len(time_values)

        if len(time_values) >= 2:
            deltas = [
                (time_values[i + 1] - time_values[i]) * seconds_per_day
                for i in range(len(time_values) - 1)
                if time_values[i + 1] > time_values[i]
            ]
            sample_interval_sec = statistics.median(deltas) if deltas else seconds_per_day
        else:
            sample_interval_sec = seconds_per_day

        return ScadaTimeSeries(
            sensor_id=f"cmg:{vector_name}",
            sample_count=sample_count,
            sample_interval_sec=sample_interval_sec,
        )
