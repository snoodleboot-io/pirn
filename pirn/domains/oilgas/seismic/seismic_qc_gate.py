"""``SeismicQCGate`` — quality-check seismic data and raise ValueError on failing datasets."""

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
        max_null_pct: float,
        min_fold: int,
        max_amplitude: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
        self._max_null_pct = float(max_null_pct)
        self._min_fold = min_fold
        self._max_amplitude = float(max_amplitude)
        super().__init__(data=data, _config=_config, **kwargs)

    async def process(self, data: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Run QC checks and return pass/fail status with trace count and issues.

        Args:
            data: Dict with ``traces`` (list) and ``fold`` (int).

        Returns:
            Dict with ``passed`` (bool), ``trace_count`` (int), and
            ``issues`` (list[str]).
        """
        if not isinstance(data, dict):
            raise TypeError("SeismicQCGate: data must be a dict")
        fold: int = int(data.get("fold", 0))
        traces: list[Any] = data.get("traces", [])
        if fold < self._min_fold:
            raise ValueError(
                f"SeismicQCGate: fold {fold} is below minimum {self._min_fold}"
            )
        null_count = sum(1 for t in traces if t is None)
        null_pct = (null_count / len(traces) * 100.0) if traces else 0.0
        if null_pct > self._max_null_pct:
            raise ValueError(
                f"SeismicQCGate: null_pct {null_pct:.1f} exceeds max {self._max_null_pct}"
            )
        issues: list[str] = []
        return {
            "passed": True,
            "trace_count": len(traces),
            "issues": issues,
        }
