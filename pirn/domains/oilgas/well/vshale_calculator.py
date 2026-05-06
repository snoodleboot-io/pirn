"""``VshaleCalculator`` — compute volume of shale from gamma ray log.

Algorithm:
    1. Receive a gamma-ray log list and positive ``gr_clean``,
       ``gr_shale``, and a ``method`` string.
    2. Validate that ``gr_clean`` and ``gr_shale`` are positive, ``gr_shale``
       exceeds ``gr_clean``, and ``method`` is supported.
    3. Compute the gamma-ray index (IGR) for each sample.
    4. Apply the selected transform (linear, Larionov older, Larionov
       tertiary, or Clavier) to convert IGR to Vshale.
    5. Return the log curve augmented with ``vshale`` values.

Math:
    Gamma-ray index:

    $$I_{GR} = \\frac{GR - GR_{clean}}{GR_{shale} - GR_{clean}}$$

    Larionov older-rock transform:

    $$V_{sh} = 0.33 \\bigl(2^{2 I_{GR}} - 1\\bigr)$$

    Clavier transform:

    $$V_{sh} = 1.7 - \\sqrt{3.38 - (I_{GR} + 0.7)^2}$$

References:
    - Larionov, V.V. (1969). *Borehole Radiometry*. Nedra, Moscow
      (gamma-ray Vshale transforms).
    - Clavier, C., Hoyle, W. & Meunier, D. (1971). Quantitative
      interpretation of thermal neutron decay time logs. *JPT*, 23(6),
      743-755. SPE-2658-PA.
"""

from __future__ import annotations

import math
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class VshaleCalculator(Knot):
    """Compute Vshale from a gamma ray log using linear or non-linear transforms."""

    def __init__(
        self,
        *,
        gr_log: Knot,
        gr_clean: Knot | float,
        gr_shale: Knot | float,
        method: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            gr_log=gr_log,
            gr_clean=gr_clean,
            gr_shale=gr_shale,
            method=method,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _igr(gr_api: float, gr_clean: float, gr_shale: float) -> float:
        denom = gr_shale - gr_clean
        return max(0.0, min(1.0, (gr_api - gr_clean) / denom)) if denom else 0.0

    @staticmethod
    def _vshale(igr: float, method: str) -> float:
        if method == "linear":
            return igr
        if method == "larionov_older":
            return 0.33 * (2.0 ** (2.0 * igr) - 1.0)
        if method == "larionov_tertiary":
            return 0.083 * (2.0 ** (3.7 * igr) - 1.0)
        # clavier
        return 1.7 - math.sqrt(3.38 - (igr + 0.7) ** 2)

    async def process(
        self,
        gr_log: list[dict[str, Any]],
        gr_clean: float,
        gr_shale: float,
        method: str,
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Compute Vshale for each log sample using the configured transform.

        Args:
            gr_log: List of dicts with ``depth_ft`` and ``gr_api``.
            gr_clean: Positive clean-sand gamma-ray baseline (API units).
            gr_shale: Positive shale gamma-ray value (API units); must exceed ``gr_clean``.
            method: Transform name; must be one of ``linear``,
                ``larionov_older``, ``larionov_tertiary``, or ``clavier``.

        Returns:
            List of dicts with ``depth_ft``, ``gr_api``, and ``vshale``.
        """
        for label, value in (("gr_clean", gr_clean), ("gr_shale", gr_shale)):
            if not isinstance(value, (int, float)):
                raise TypeError(f"VshaleCalculator: {label} must be numeric")
            if value <= 0:
                raise ValueError(f"VshaleCalculator: {label} must be positive")
        if gr_shale <= gr_clean:
            raise ValueError(
                "VshaleCalculator: gr_shale must be greater than gr_clean"
            )
        _valid_methods = frozenset({"linear", "larionov_older", "larionov_tertiary", "clavier"})
        if method not in _valid_methods:
            raise ValueError(
                f"VshaleCalculator: method must be one of {sorted(_valid_methods)}"
            )
        results: list[dict[str, Any]] = []
        for entry in gr_log:
            gr = float(entry.get("gr_api", 0.0))
            igr = self._igr(gr, float(gr_clean), float(gr_shale))
            vsh = max(0.0, min(1.0, self._vshale(igr, method)))
            results.append({**entry, "vshale": vsh})
        return results
