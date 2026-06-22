"""``SpirometryAnalyzer`` — derive FEV1 / FVC / PEF from a spirometry trace.

Algorithm:
    1. Receive flow_l_per_sec sequence of floats and sample_rate_hz.
    2. Validate flow_l_per_sec is a list/tuple of numeric values.
    3. Validate sample_rate_hz is a positive number.
    4. Integrate the flow signal to obtain cumulative volume.
    5. Compute FVC, FEV1, FEV1/FVC ratio, and PEF from the derived curves.

Math:
    Volume from flow (numerical integration):

    $$V(t) = \\int_0^t \\dot{V}(\\tau)\\, d\\tau \\approx \\sum_{k=0}^{t} \\dot{V}_k \\cdot \\Delta t$$

    where $\\Delta t = 1 / \\text{sample\\_rate\\_hz}$.

References:
    - Miller, M.R., et al. (2005). Standardisation of spirometry. Eur Respir J.
    - ATS/ERS Task Force (2005). Standardisation of lung function testing.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


def _analyze_spirometry(flow_or_volume: np.ndarray, fs: float) -> dict[str, float]:
    """Compute FVC, FEV1, FEV1/FVC ratio, and PEF from a flow or volume signal.

    Args:
        flow_or_volume: 1-D array of flow values in L/s.
        fs: Sampling rate in Hz.

    Returns:
        Dict with fvc, fev1, fev1_fvc_ratio, pef, and predicted_fvc_pct.
    """
    if flow_or_volume.size == 0 or fs <= 0:
        return {
            "fvc": 0.0,
            "fev1": 0.0,
            "fev1_fvc_ratio": 0.0,
            "pef": 0.0,
            "predicted_fvc_pct": 100.0,
        }
    dt = 1.0 / fs
    volume = np.cumsum(flow_or_volume) * dt
    fvc = float(volume.max()) if volume.size > 0 else 0.0
    samples_1sec = min(int(fs), flow_or_volume.size)
    fev1 = float(volume[samples_1sec - 1]) if samples_1sec > 0 else 0.0
    fev1_fvc_ratio = (fev1 / fvc) if fvc > 0 else 0.0
    pef = float(flow_or_volume.max()) if flow_or_volume.size > 0 else 0.0
    predicted_fvc_pct = 100.0
    return {
        "fvc": fvc,
        "fev1": fev1,
        "fev1_fvc_ratio": fev1_fvc_ratio,
        "pef": pef,
        "predicted_fvc_pct": predicted_fvc_pct,
    }


class SpirometryAnalyzer(Knot):
    """Compute spirometry indices from a flow-volume trace."""

    def __init__(
        self,
        *,
        flow_l_per_sec: Knot | Sequence[float],
        sample_rate_hz: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            flow_l_per_sec=flow_l_per_sec,
            sample_rate_hz=sample_rate_hz,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        flow_l_per_sec: Sequence[float],
        sample_rate_hz: float,
        **_: Any,
    ) -> Mapping[str, float]:
        """Derive FEV1, FVC, FEV1/FVC ratio, and PEF from the flow-volume trace.

        Args:
            flow_l_per_sec: Sequence of flow values in litres per second.
            sample_rate_hz: Sample rate of the flow signal in Hz (must be > 0).

        Returns:
            Mapping of metric name to float value, including fvc, fev1,
            fev1_fvc_ratio, pef, and predicted_fvc_pct.

        Raises:
            TypeError: If flow_l_per_sec is not list/tuple or contains non-numeric values.
            ValueError: If sample_rate_hz is not a positive number.
        """
        if not isinstance(flow_l_per_sec, (list, tuple)):
            raise TypeError("SpirometryAnalyzer: flow_l_per_sec must be list/tuple")
        for flow_value in flow_l_per_sec:
            if not isinstance(flow_value, (int, float)):
                raise TypeError("SpirometryAnalyzer: every flow value must be numeric")
        if not isinstance(sample_rate_hz, (int, float)) or float(sample_rate_hz) <= 0:
            raise ValueError("SpirometryAnalyzer: sample_rate_hz must be a positive number")
        flow_array = np.asarray(flow_l_per_sec, dtype=float)
        return await asyncio.to_thread(_analyze_spirometry, flow_array, float(sample_rate_hz))
