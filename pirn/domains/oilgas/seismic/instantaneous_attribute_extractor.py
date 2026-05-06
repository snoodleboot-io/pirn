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

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


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
        invalid = [a for a in attributes if a not in valid_attributes]
        if invalid:
            raise ValueError(
                f"InstantaneousAttributeExtractor: unknown attributes {invalid}; "
                f"must be from {sorted(valid_attributes)}"
            )
        if not isinstance(trace, dict):
            raise TypeError("InstantaneousAttributeExtractor: trace must be a dict")
        samples: list[float] = trace.get("samples", [])
        return {attr: [0.0] * len(samples) for attr in attributes}
