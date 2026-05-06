"""``SeismicQCGate`` — quality-check seismic data and raise ValueError on failing datasets.

Algorithm:
    1. Receive a seismic data dict, a ``max_null_pct`` threshold, a positive
       ``min_fold``, and a positive ``max_amplitude``.
    2. Validate all numeric inputs.
    3. Check the actual fold against ``min_fold`` and the null-trace
       percentage against ``max_null_pct``; raise ``ValueError`` on failure.
    4. Return a QC result dict with pass/fail status, trace count, and issues.

Math:
    Null trace percentage:

    $$p_{null} = \\frac{N_{null}}{N_{total}} \\times 100 \\quad [\\%]$$

References:
    - Brown, A.R. (2011). *Interpretation of Three-Dimensional Seismic Data*,
      7th ed. SEG/AAPG Memoir 42, Appendix A (seismic data quality criteria).
    - Liner, C.L. (2004). *Elements of 3D Seismology*, 2nd ed. PennWell,
      Chapter 3 (acquisition quality control).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class SeismicQCGate(Knot):
    """Gate seismic data through quality checks; raise on fold or null-percentage violations."""

    def __init__(
        self,
        *,
        data: Knot,
        max_null_pct: Knot | float,
        min_fold: Knot | int,
        max_amplitude: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            data=data,
            max_null_pct=max_null_pct,
            min_fold=min_fold,
            max_amplitude=max_amplitude,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        data: dict[str, Any],
        max_null_pct: float,
        min_fold: int,
        max_amplitude: float,
        **_: Any,
    ) -> dict[str, Any]:
        """Run QC checks and return pass/fail status with trace count and issues.

        Args:
            data: Dict with ``traces`` (list) and ``fold`` (int).
            max_null_pct: Maximum allowed null trace percentage in [0, 100].
            min_fold: Minimum required CMP fold (positive integer).
            max_amplitude: Maximum allowed absolute amplitude (positive float).

        Returns:
            Dict with ``passed`` (bool), ``trace_count`` (int), and
            ``issues`` (list[str]).
        """
        if not isinstance(max_null_pct, (int, float)):
            raise TypeError("SeismicQCGate: max_null_pct must be numeric")
        if not (0 <= max_null_pct <= 100):
            raise ValueError("SeismicQCGate: max_null_pct must be in [0, 100]")
        if not isinstance(min_fold, int):
            raise TypeError("SeismicQCGate: min_fold must be an int")
        if min_fold <= 0:
            raise ValueError("SeismicQCGate: min_fold must be positive")
        if not isinstance(max_amplitude, (int, float)):
            raise TypeError("SeismicQCGate: max_amplitude must be numeric")
        if max_amplitude <= 0:
            raise ValueError("SeismicQCGate: max_amplitude must be positive")
        if not isinstance(data, dict):
            raise TypeError("SeismicQCGate: data must be a dict")
        fold: int = int(data.get("fold", 0))
        traces: list[Any] = data.get("traces", [])
        if fold < min_fold:
            raise ValueError(
                f"SeismicQCGate: fold {fold} is below minimum {min_fold}"
            )
        null_count = sum(1 for t in traces if t is None)
        null_pct = (null_count / len(traces) * 100.0) if traces else 0.0
        if null_pct > max_null_pct:
            raise ValueError(
                f"SeismicQCGate: null_pct {null_pct:.1f} exceeds max {max_null_pct}"
            )
        return {
            "passed": True,
            "trace_count": len(traces),
            "issues": [],
        }
