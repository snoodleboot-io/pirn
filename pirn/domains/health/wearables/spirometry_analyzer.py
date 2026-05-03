"""``SpirometryAnalyzer`` — derive FEV1 / FVC / PEF from a spirometry trace.

Production version interprets the volume-time and flow-volume curves
and computes ATS/ERS-recommended indices. This stub returns canonical
spirometry metrics with zero values.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class SpirometryAnalyzer(Knot):
    """Compute spirometry indices from a flow-volume trace."""

    def __init__(
        self,
        *,
        flow_l_per_sec: Sequence[float],
        sample_rate_hz: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(flow_l_per_sec, (list, tuple)):
            raise TypeError(
                "SpirometryAnalyzer: flow_l_per_sec must be list/tuple"
            )
        for f in flow_l_per_sec:
            if not isinstance(f, (int, float)):
                raise TypeError(
                    "SpirometryAnalyzer: every flow value must be numeric"
                )
        if (
            not isinstance(sample_rate_hz, (int, float))
            or float(sample_rate_hz) <= 0
        ):
            raise ValueError(
                "SpirometryAnalyzer: sample_rate_hz must be a positive number"
            )
        self._flow = tuple(float(f) for f in flow_l_per_sec)
        self._sample_rate = float(sample_rate_hz)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Mapping[str, float]:
        """Derive FEV1, FVC, FEV1/FVC ratio, and PEF from the flow-volume trace and return the metric mapping.

        Returns:
            Mapping of metric name to float value, including fev1_l, fvc_l,
            fev1_fvc_ratio, and pef_l_per_sec.
        """
        return {
            "fev1_l": 0.0,
            "fvc_l": 0.0,
            "fev1_fvc_ratio": 0.0,
            "pef_l_per_sec": 0.0,
        }
