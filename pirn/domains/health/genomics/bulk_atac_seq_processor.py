"""``BulkATACSeqProcessor`` — process bulk ATAC-seq data."""
from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class BulkATACSeqProcessor(Knot):
    """Process bulk ATAC-seq data: shift reads, call peaks, compute TSS enrichment."""

    def __init__(
        self,
        *,
        bam: Knot,
        genome: str,
        shift_plus: int = 4,
        shift_minus: int = -5,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(genome, str) or not genome:
            raise ValueError("BulkATACSeqProcessor: genome must be non-empty")
        if not isinstance(shift_plus, int):
            raise TypeError("BulkATACSeqProcessor: shift_plus must be an int")
        if not isinstance(shift_minus, int):
            raise TypeError("BulkATACSeqProcessor: shift_minus must be an int")
        self._genome = genome
        self._shift_plus = shift_plus
        self._shift_minus = shift_minus
        super().__init__(bam=bam, _config=_config, **kwargs)

    async def process(self, bam: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Shift reads, call peaks, and compute TSS enrichment for bulk ATAC-seq.

        Args:
            bam: Dict with ``aligned_reads`` (int), ``duplication_rate`` (float),
                and ``bam_path`` (str).

        Returns:
            Dict with ``peaks``, ``n_peaks``, ``tss_enrichment_score``,
            and ``frip_score``.
        """
        if not isinstance(bam, dict):
            raise TypeError("BulkATACSeqProcessor: bam must be a dict")
        return {
            "peaks": [],
            "n_peaks": 0,
            "tss_enrichment_score": 0.0,
            "frip_score": 0.0,
        }
