"""``AdapterTrimmer`` — trim sequencing adapters from FASTQ reads.

Algorithm:
    1. Receive a FASTQ dict, adapter_sequence string, min_length int, and quality_cutoff int.
    2. Validate types and that adapter_sequence is non-empty, min_length > 0, quality_cutoff in [0, 40].
    3. For each read, find and remove the adapter sequence.
    4. Discard reads shorter than min_length after trimming.
    5. Return trimming statistics and the trimmed reads.


References:
    - Trimmomatic: http://www.usadellab.org/cms/?page=trimmomatic
    - Cutadapt: https://cutadapt.readthedocs.io/
"""
from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class AdapterTrimmer(Knot):
    """Trim sequencing adapters from FASTQ reads."""

    def __init__(
        self,
        *,
        fastq: Knot | dict[str, Any],
        adapter_sequence: Knot | str,
        min_length: Knot | int,
        quality_cutoff: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            fastq=fastq,
            adapter_sequence=adapter_sequence,
            min_length=min_length,
            quality_cutoff=quality_cutoff,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        fastq: dict[str, Any],
        adapter_sequence: str,
        min_length: int,
        quality_cutoff: int,
        **_: Any,
    ) -> dict[str, Any]:
        """Trim adapters from FASTQ reads using the configured adapter sequence.

        Args:
            fastq: Dict with ``reads`` (list of dicts with id/sequence/quality)
                and ``total_reads`` (int).
            adapter_sequence: Non-empty adapter sequence string to trim.
            min_length: Minimum read length after trimming (positive int).
            quality_cutoff: Quality score cutoff in [0, 40].

        Returns:
            Dict with ``trimmed_reads``, ``n_trimmed``, ``mean_trimmed_length``,
            and ``adapter_sequence``.

        Raises:
            TypeError: If fastq is not a dict.
            ValueError: If adapter_sequence is empty, min_length <= 0, or quality_cutoff out of range.
        """
        if not isinstance(adapter_sequence, str) or not adapter_sequence:
            raise ValueError("AdapterTrimmer: adapter_sequence must be non-empty")
        if not isinstance(min_length, int) or min_length <= 0:
            raise ValueError("AdapterTrimmer: min_length must be > 0")
        if not isinstance(quality_cutoff, int) or not (0 <= quality_cutoff <= 40):
            raise ValueError("AdapterTrimmer: quality_cutoff must be in [0, 40]")
        if not isinstance(fastq, dict):
            raise TypeError("AdapterTrimmer: fastq must be a dict")
        reads: list[dict[str, Any]] = fastq.get("reads", [])
        trimmed: list[dict[str, Any]] = []
        for read in reads:
            seq: str = read.get("sequence", "")
            idx = seq.find(adapter_sequence)
            clipped = seq[:idx] if idx != -1 else seq
            if len(clipped) >= min_length:
                trimmed.append({**read, "sequence": clipped})
        lengths = [len(r["sequence"]) for r in trimmed] if trimmed else [0]
        mean_len = sum(lengths) / len(lengths)
        return {
            "trimmed_reads": trimmed,
            "n_trimmed": len(reads) - len(trimmed),
            "mean_trimmed_length": mean_len,
            "adapter_sequence": adapter_sequence,
        }
