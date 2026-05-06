"""``MudLoggingIngester`` — parse and ingest mud log data.

Algorithm:
    1. Receive a raw mud log dict and a ``required_curves`` tuple of
       expected column names.
    2. Validate that the input is a dict.
    3. Check that all required curve names are present in the first data row.
    4. Return a structured dict with well name, record count, curve list,
       and data rows.


References:
    - IADC Mud Logging Manual (1999), Section 3 (mud log data recording and
      quality control).
    - Swanson, B.F. (1981). A simple correlation between permeabilities and
      mercury capillary pressures. *JPT*, 33(12), 2498–2504. (mud-log
      gas-show interpretation context.)
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class MudLoggingIngester(Knot):
    """Parse mud log data (cuttings, gas shows, ROP, drilling parameters)."""

    def __init__(
        self,
        *,
        raw_mud_log: Knot,
        required_curves: Knot | tuple[str, ...] = ("depth_ft", "rop_ft_hr", "gas_units"),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            raw_mud_log=raw_mud_log,
            required_curves=required_curves,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        raw_mud_log: dict[str, Any],
        required_curves: tuple[str, ...] = ("depth_ft", "rop_ft_hr", "gas_units"),
        **_: Any,
    ) -> dict[str, Any]:
        """Parse the mud log and validate required curves are present.

        Args:
            raw_mud_log: Dict with ``header`` (dict) and ``data``
                (list of dicts containing curve data rows).
            required_curves: Tuple of curve names that must be present in
                every data row.

        Returns:
            Dict with ``well_name`` (str), ``record_count`` (int),
            ``curves`` (list[str]), and ``data`` (list).
        """
        if not isinstance(raw_mud_log, dict):
            raise TypeError("MudLoggingIngester: raw_mud_log must be a dict")
        data: list[dict[str, Any]] = raw_mud_log.get("data", [])
        if data:
            first_row_keys = set(data[0].keys())
            missing = [c for c in required_curves if c not in first_row_keys]
            if missing:
                raise ValueError(
                    f"MudLoggingIngester: missing required curves: {missing}"
                )
        header: dict[str, Any] = raw_mud_log.get("header", {})
        curves = list(data[0].keys()) if data else list(required_curves)
        return {
            "well_name": header.get("well_name", "unknown"),
            "record_count": len(data),
            "curves": curves,
            "data": data,
        }
