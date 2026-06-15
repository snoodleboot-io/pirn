"""``InstantaneousAttributeExtractor`` — compute Hilbert-transform-based instantaneous seismic attributes.

Algorithm:
    1. Receive a seismic trace dict and a tuple of requested attribute names.
    2. Validate that every requested attribute is in the supported set.
    3. Compute the analytic signal via the Hilbert transform.
    4. Derive each instantaneous attribute (amplitude envelope, phase,
       instantaneous frequency, etc.) from the analytic signal.
    5. Return a dict mapping each attribute name to its sample array.

Math:
    Analytic signal:

    $$\\tilde{s}(t) = s(t) + i \\, \\mathcal{H}\\{s(t)\\}$$

    Instantaneous attributes:

    $$A(t) = |\\tilde{s}(t)|, \\quad
      \\phi(t) = \\arg\\tilde{s}(t), \\quad
      f(t) = \\frac{1}{2\\pi} \\frac{d\\phi}{dt}$$

References:
    - Taner, M.T., Koehler, F. & Sheriff, R.E. (1979). Complex seismic trace
      analysis. *Geophysics*, 44(6), 1041-1063.
    - Barnes, A.E. (1993). Instantaneous spectral bandwidth and dominant
      frequency with applications to seismic reflection data. *Geophysics*,
      58(3), 419-428.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from scipy.signal import hilbert


class InstantaneousAttributeExtractor(Knot):
    """Extract instantaneous seismic attributes via Hilbert transform."""

    def __init__(
        self,
        *,
        trace: Knot,
        attributes: Knot | tuple[str, ...] = ("amplitude", "phase", "frequency"),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            trace=trace,
            attributes=attributes,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        trace: dict[str, Any],
        attributes: tuple[str, ...] = ("amplitude", "phase", "frequency"),
        **_: Any,
    ) -> dict[str, Any]:
        """Compute instantaneous attributes from a seismic trace.

        Args:
            trace: Dict with ``samples`` (list[float]) and
                ``sample_interval_ms`` (float).
            attributes: Tuple of attribute names to compute. Each must be one
                of ``amplitude``, ``phase``, ``frequency``, ``bandwidth``,
                or ``q_factor``.

        Returns:
            Dict with one key per requested attribute, each value is list[float].
        """
        valid_attributes: frozenset[str] = frozenset(
            {"amplitude", "phase", "frequency", "bandwidth", "q_factor"}
        )
        invalid = [attr_name for attr_name in attributes if attr_name not in valid_attributes]
        if invalid:
            raise ValueError(
                f"InstantaneousAttributeExtractor: unknown attributes {invalid}; "
                f"must be from {sorted(valid_attributes)}"
            )
        if not isinstance(trace, dict):
            raise TypeError("InstantaneousAttributeExtractor: trace must be a dict")
        samples: list[float] = trace.get("samples", [])
        dt: float = float(trace.get("sample_interval_ms", 4.0)) * 1e-3
        arr = np.asarray(samples, dtype=np.float64)
        result: dict[str, list[float]] = {}
        if len(arr) == 0:
            return {attr: [] for attr in attributes}
        analytic: np.ndarray = np.asarray(hilbert(arr))
        amp = np.abs(analytic)
        phase = np.unwrap(np.angle(analytic))
        inst_freq = np.diff(phase, prepend=phase[0]) / (2.0 * np.pi * dt)
        for attr in attributes:
            if attr == "amplitude":
                result[attr] = amp.tolist()
            elif attr == "phase":
                result[attr] = phase.tolist()
            elif attr == "frequency":
                result[attr] = inst_freq.tolist()
            elif attr == "bandwidth":
                d_amp = np.diff(amp, prepend=amp[0])
                bw = np.abs(d_amp) / (amp + 1e-12) / (2.0 * np.pi * dt)
                result[attr] = bw.tolist()
            elif attr == "q_factor":
                bw_val = np.abs(np.diff(amp, prepend=amp[0])) / (amp + 1e-12) / (2.0 * np.pi * dt)
                quality_factor = np.abs(inst_freq) / (bw_val + 1e-12)
                result[attr] = quality_factor.tolist()
        return result
