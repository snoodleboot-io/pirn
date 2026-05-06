"""``VCFFilter`` — quality / frequency filter over VCF rows.

Production version streams a VCF via ``pysam.VariantFile`` and applies
``min_qual`` / ``max_af`` thresholds. This stub keeps the orchestration
shape: in-memory tuple of dicts → filtered tuple.

Algorithm:
    1. Receive rows sequence, min_qual float, and max_af float.
    2. Validate rows is list/tuple of Mappings, min_qual and max_af are numeric, max_af in [0, 1].
    3. For each row, extract qual and af fields.
    4. Keep rows where qual >= min_qual and af <= max_af.
    5. Return filtered rows as a tuple.

Math:
    Filter predicate:

    $$\\text{keep}(r) = \\mathbf{1}[r.\\text{qual} \\geq q_{\\min}] \\cdot \\mathbf{1}[r.\\text{af} \\leq f_{\\max}]$$

References:
    - VCF specification: https://samtools.github.io/hts-specs/VCFv4.3.pdf
    - pysam: https://pysam.readthedocs.io/
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
        rows: Knot | Sequence[Mapping[str, Any]],
        min_qual: Knot | float,
        max_af: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rows=rows,
            min_qual=min_qual,
            max_af=max_af,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        rows: Sequence[Mapping[str, Any]],
        min_qual: float,
        max_af: float,
        **_: Any,
    ) -> tuple[Mapping[str, Any], ...]:
        """Filter VCF rows by the configured minimum quality and maximum allele-frequency thresholds.

        Args:
            rows: List or tuple of Mapping row dicts each with qual and af fields.
            min_qual: Minimum quality threshold (numeric).
            max_af: Maximum allele frequency threshold in [0, 1] (numeric).

        Returns:
            Tuple of row dicts that pass both the quality and allele-frequency filters.

        Raises:
            TypeError: If rows is not list/tuple, contains non-Mappings, or thresholds are not numeric.
            ValueError: If max_af is outside [0, 1].
        """
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
        q = float(min_qual)
        f = float(max_af)
        out: list[Mapping[str, Any]] = []
        for row in rows:
            try:
                qual = float(row.get("qual", 0.0))
                af = float(row.get("af", 0.0))
            except (TypeError, ValueError):
                continue
            if qual >= q and af <= f:
                out.append(dict(row))
        return tuple(out)
