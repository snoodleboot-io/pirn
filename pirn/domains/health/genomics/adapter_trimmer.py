"""``AdapterTrimmer`` — trim sequencing adapters from FASTQ reads."""
from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class AdapterTrimmer(Knot):
    """Trim sequencing adapters from FASTQ reads."""

    def __init__(
        self,
        *,
        fastq: Knot,
        adapter_sequence: str,
        min_length: int,
        quality_cutoff: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(adapter_sequence, str) or not adapter_sequence:
            raise ValueError("AdapterTrimmer: adapter_sequence must be non-empty")
        if not isinstance(min_length, int) or min_length <= 0:
            raise ValueError("AdapterTrimmer: min_length must be > 0")
        if not isinstance(quality_cutoff, int) or not (0 <= quality_cutoff <= 40):
            raise ValueError("AdapterTrimmer: quality_cutoff must be in [0, 40]")
        self._adapter_sequence = adapter_sequence
        self._min_length = min_length
        self._quality_cutoff = quality_cutoff
        super().__init__(fastq=fastq, _config=_config, **kwargs)

    async def process(self, fastq: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Trim adapters from FASTQ reads using the configured adapter sequence.

        Args:
            fastq: Dict with ``reads`` (list of dicts with id/sequence/quality)
                and ``total_reads`` (int).

        Returns:
            Dict with ``trimmed_reads``, ``n_trimmed``, ``mean_trimmed_length``,
            and ``adapter_sequence``.
        """
        if not isinstance(fastq, dict):
            raise TypeError("AdapterTrimmer: fastq must be a dict")
        reads: list[dict[str, Any]] = fastq.get("reads", [])
        trimmed: list[dict[str, Any]] = []
        for read in reads:
            seq: str = read.get("sequence", "")
            idx = seq.find(self._adapter_sequence)
            clipped = seq[:idx] if idx != -1 else seq
            if len(clipped) >= self._min_length:
                trimmed.append({**read, "sequence": clipped})
        lengths = [len(r["sequence"]) for r in trimmed] if trimmed else [0]
        mean_len = sum(lengths) / len(lengths)
        return {
            "trimmed_reads": trimmed,
            "n_trimmed": len(reads) - len(trimmed),
            "mean_trimmed_length": mean_len,
            "adapter_sequence": self._adapter_sequence,
        }
