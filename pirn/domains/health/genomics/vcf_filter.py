"""``VCFFilter`` — quality / frequency filter over VCF rows.

Production version streams a VCF via ``pysam.VariantFile`` and applies
``min_qual`` / ``max_af`` thresholds. This stub keeps the orchestration
shape: in-memory tuple of dicts → filtered tuple.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class VCFFilter(Knot):
    """Filter VCF-shaped row dicts by quality and allele-frequency bounds."""

    def __init__(
        self,
        *,
        rows: Sequence[Mapping[str, Any]],
        min_qual: float,
        max_af: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(rows, (list, tuple)):
            raise TypeError("VCFFilter: rows must be a list or tuple")
        for row in rows:
            if not isinstance(row, Mapping):
                raise TypeError("VCFFilter: every row must be a Mapping")
        if not isinstance(min_qual, (int, float)):
            raise TypeError("VCFFilter: min_qual must be numeric")
        if not isinstance(max_af, (int, float)):
            raise TypeError("VCFFilter: max_af must be numeric")
        if not 0.0 <= float(max_af) <= 1.0:
            raise ValueError("VCFFilter: max_af must be in [0, 1]")
        self._rows = tuple(dict(r) for r in rows)
        self._min_qual = float(min_qual)
        self._max_af = float(max_af)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> tuple[Mapping[str, Any], ...]:
        out: list[Mapping[str, Any]] = []
        for row in self._rows:
            try:
                qual = float(row.get("qual", 0.0))
                af = float(row.get("af", 0.0))
            except (TypeError, ValueError):
                continue
            if qual >= self._min_qual and af <= self._max_af:
                out.append(row)
        return tuple(out)
