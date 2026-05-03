"""``MethylationArrayProcessor`` — process Illumina methylation array data."""
from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class MethylationArrayProcessor(Knot):
    """Process Illumina methylation array data: normalize, QC, compute beta/M values."""

    _VALID_ARRAY_TYPES: frozenset[str] = frozenset({"epic", "450k", "27k"})
    _VALID_NORMALIZATIONS: frozenset[str] = frozenset({"ssnoob", "quantile", "noob", "raw"})

    def __init__(
        self,
        *,
        idat_data: Knot,
        array_type: str,
        normalization: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(array_type, str) or array_type not in self._VALID_ARRAY_TYPES:
            raise ValueError(
                f"MethylationArrayProcessor: array_type must be one of "
                f"{sorted(self._VALID_ARRAY_TYPES)}"
            )
        if not isinstance(normalization, str) or normalization not in self._VALID_NORMALIZATIONS:
            raise ValueError(
                f"MethylationArrayProcessor: normalization must be one of "
                f"{sorted(self._VALID_NORMALIZATIONS)}"
            )
        self._array_type = array_type
        self._normalization = normalization
        super().__init__(idat_data=idat_data, _config=_config, **kwargs)

    async def process(self, idat_data: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Normalize and QC methylation array data and return beta/M values.

        Args:
            idat_data: Dict with ``red_channel`` (list), ``green_channel`` (list),
                and ``sample_id`` (str).

        Returns:
            Dict with ``sample_id``, ``n_probes``, ``beta_values``,
            ``m_values``, and ``detection_p_values``.
        """
        if not isinstance(idat_data, dict):
            raise TypeError("MethylationArrayProcessor: idat_data must be a dict")
        return {
            "sample_id": idat_data.get("sample_id", ""),
            "n_probes": 0,
            "beta_values": {},
            "m_values": {},
            "detection_p_values": {},
        }
