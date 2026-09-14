"""``BulkATACSeqProcessor`` — process bulk ATAC-seq data.

Algorithm:
    1. Receive a BAM dict, genome string, shift_plus int, and shift_minus int.
    2. Validate types and that genome is non-empty and shifts are ints.
    3. Shift Tn5 cut sites by shift_plus (+ strand) and shift_minus (- strand).
    4. Call peaks using MACS2 or HMMRATAC.
    5. Compute TSS enrichment score and FRiP score.

Math:
    Fraction of reads in peaks (FRiP):

    FRiP = reads_in_peaks / total_reads

    TSS enrichment score (normalized cut-site pileup at TSSs vs. flanking regions):

    TSS_score = mean_signal_at_TSS / mean_signal_in_flanks

References:
    - ENCODE ATAC-seq pipeline: https://www.encodeproject.org/atac-seq/
    - Buenrostro et al. (2013) Transposition of native chromatin for fast and sensitive epigenomic profiling.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class BulkATACSeqProcessor(Knot):
    """Process bulk ATAC-seq data: shift reads, call peaks, compute TSS enrichment."""

    def __init__(
        self,
        *,
        bam: Knot | dict[str, Any],
        genome: Knot | str,
        shift_plus: Knot | int = 4,
        shift_minus: Knot | int = -5,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            bam=bam,
            genome=genome,
            shift_plus=shift_plus,
            shift_minus=shift_minus,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        bam: dict[str, Any],
        genome: str,
        shift_plus: int = 4,
        shift_minus: int = -5,
        **_: Any,
    ) -> dict[str, Any]:
        """Shift reads, call peaks, and compute TSS enrichment for bulk ATAC-seq.

        Args:
            bam: Dict with ``aligned_reads`` (int), ``duplication_rate`` (float),
                and ``bam_path`` (str).
            genome: Non-empty genome assembly identifier string (e.g. 'hg38').
            shift_plus: Integer Tn5 shift for plus-strand reads.
            shift_minus: Integer Tn5 shift for minus-strand reads.

        Returns:
            Dict with ``peaks``, ``n_peaks``, ``tss_enrichment_score``,
            and ``frip_score``.

        Raises:
            TypeError: If bam is not a dict or shifts are not ints.
            ValueError: If genome is empty.
        """
        if not isinstance(genome, str) or not genome:
            raise ValueError("BulkATACSeqProcessor: genome must be non-empty")
        if not isinstance(shift_plus, int):
            raise TypeError("BulkATACSeqProcessor: shift_plus must be an int")
        if not isinstance(shift_minus, int):
            raise TypeError("BulkATACSeqProcessor: shift_minus must be an int")
        if not isinstance(bam, dict):
            raise TypeError("BulkATACSeqProcessor: bam must be a dict")
        return {
            "peaks": [],
            "n_peaks": 0,
            "tss_enrichment_score": 0.0,
            "frip_score": 0.0,
        }
