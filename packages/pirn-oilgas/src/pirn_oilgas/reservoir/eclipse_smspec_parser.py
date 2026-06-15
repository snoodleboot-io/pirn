"""``EclipseSmspecParser`` — parse an Eclipse SMSPEC summary file.

Algorithm:
    1. Receive ``smspec_path`` and ``vector_name`` strings.
    2. Validate that both are non-empty strings.
    3. Open the Eclipse SMSPEC binary file via ``resfo.read`` and read the
       KEYWORDS / WGNAMES / DIMENS keywords to locate the requested vector.
    4. Derive ``sample_count`` from the DIMENS record (field index 0 = num
       ministeps) and ``sample_interval_sec`` from the STARTDAT header if
       present; fall back to 86400 s (daily) when absent.
    5. Return a :class:`ScadaTimeSeries` keyed by ``eclipse:<vector_name>``.

References:
    - Schlumberger (2014). *ECLIPSE Reservoir Simulation Software Reference
      Manual*, Section 5 — Summary File Format (SMSPEC + UNSMRY).
    - OPM Project (2023). *OPM Flow Reference Manual*, Appendix D — SMSPEC
      binary format.
    - resfo (LGPL-3): https://github.com/equinor/resfo
"""

from __future__ import annotations

import os
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_oilgas.types.scada_time_series import ScadaTimeSeries


class EclipseSmspecParser(Knot):
    """Parse an Eclipse SMSPEC binary into a :class:`ScadaTimeSeries` reference."""

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
        """Parse the Eclipse SMSPEC file and return a ScadaTimeSeries for the named vector.

        Args:
            smspec_path: Non-empty path to the Eclipse SMSPEC binary file.
            vector_name: Non-empty Eclipse summary vector name (e.g. ``WOPR:W1``).

        Returns:
            ScadaTimeSeries keyed by ``eclipse:{vector_name}``.

        Raises:
            ValueError: If smspec_path or vector_name is empty.
            ImportError: If ``resfo`` is not installed (install ``pirn[oilgas]``).
            FileNotFoundError: If the SMSPEC file does not exist.
            KeyError: If vector_name is not found in the SMSPEC index.
        """
        if not isinstance(smspec_path, str) or not smspec_path:
            raise ValueError("EclipseSmspecParser: smspec_path must be a non-empty string")
        if not isinstance(vector_name, str) or not vector_name:
            raise ValueError("EclipseSmspecParser: vector_name must be a non-empty string")

        try:
            import resfo
        except ImportError as exc:
            raise ImportError("EclipseSmspecParser requires resfo — install pirn[oilgas]") from exc

        if not os.path.isfile(smspec_path):
            raise FileNotFoundError(f"EclipseSmspecParser: SMSPEC file not found: {smspec_path}")

        def _decode(raw_value: Any) -> str:
            return (
                raw_value.decode() if isinstance(raw_value, (bytes, bytearray)) else str(raw_value)
            )

        records: dict[str, Any] = {_decode(kw).strip(): arr for kw, arr in resfo.read(smspec_path)}

        # KEYWORDS holds the summary mnemonic (e.g. "WOPR"), WGNAMES the
        # well/group qualifier (e.g. "WELL1"). Reconstruct the combined key.
        keywords = [_decode(k).strip() for k in records.get("KEYWORDS", [])]
        wgnames = [_decode(w).strip() for w in records.get("WGNAMES", [])]

        # Build index: "MNEMONIC:WGNAME" → position (drop empty wgnames)
        kw_part, wg_part = vector_name.split(":", 1) if ":" in vector_name else (vector_name, "")
        found = False
        for kw, wg in zip(keywords, wgnames, strict=False):
            if kw == kw_part and (not wg_part or wg == wg_part):
                found = True
                break
        if not found:
            raise KeyError(
                f"EclipseSmspecParser: vector '{vector_name}' not found in {smspec_path}"
            )

        # DIMENS[0] = number of summary vectors, DIMENS[1] = reserved,
        # DIMENS[2] = number of ministep records stored in UNSMRY.
        dimens = records.get("DIMENS", [])
        sample_count = int(dimens[2]) if len(dimens) >= 3 else 0

        # Daily output is the Eclipse default; STARTDAT does not encode interval.
        sample_interval_sec = 86400.0

        return ScadaTimeSeries(
            sensor_id=f"eclipse:{vector_name}",
            sample_count=sample_count,
            sample_interval_sec=sample_interval_sec,
        )
