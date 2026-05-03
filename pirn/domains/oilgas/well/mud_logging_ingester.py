"""``MudLoggingIngester`` — parse and ingest mud log data."""

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
        required_curves: tuple[str, ...] = ("depth_ft", "rop_ft_hr", "gas_units"),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        self._required_curves = required_curves
        super().__init__(raw_mud_log=raw_mud_log, _config=_config, **kwargs)

    async def process(self, raw_mud_log: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Parse the mud log and validate required curves are present.

        Args:
            raw_mud_log: Dict with ``header`` (dict) and ``data``
                (list of dicts containing curve data rows).

        Returns:
            Dict with ``well_name`` (str), ``record_count`` (int),
            ``curves`` (list[str]), and ``data`` (list).
        """
        if not isinstance(raw_mud_log, dict):
            raise TypeError("MudLoggingIngester: raw_mud_log must be a dict")
        data: list[dict[str, Any]] = raw_mud_log.get("data", [])
        if data:
            first_row_keys = set(data[0].keys())
            missing = [c for c in self._required_curves if c not in first_row_keys]
            if missing:
                raise ValueError(
                    f"MudLoggingIngester: missing required curves: {missing}"
                )
        header: dict[str, Any] = raw_mud_log.get("header", {})
        curves = list(data[0].keys()) if data else list(self._required_curves)
        return {
            "well_name": header.get("well_name", "unknown"),
            "record_count": len(data),
            "curves": curves,
            "data": data,
        }
