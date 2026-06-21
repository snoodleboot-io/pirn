"""``VCFMerger`` — merge per-sample VCFs into a cohort VCF.

Production version uses ``bcftools merge`` or ``pysam`` to align
sites across samples; this stub validates inputs and returns the
target output path.

Algorithm:
    1. Receive vcf_paths sequence and output_vcf_path string.
    2. Validate vcf_paths is a non-empty list/tuple of non-empty strings.
    3. Validate output_vcf_path is a non-empty string.
    4. Merge per-sample VCF records by genomic position across all input files.
    5. Return the path to the merged cohort VCF.


References:
    - bcftools merge: https://samtools.github.io/bcftools/bcftools.html#merge
    - VCF specification: https://samtools.github.io/hts-specs/VCFv4.3.pdf
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


async def _run_subprocess(cmd: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {stderr.decode()}")


class VCFMerger(Knot):
    """Merge multiple VCF paths into a single cohort VCF."""

    def __init__(
        self,
        *,
        vcf_paths: Knot | Sequence[str],
        output_vcf_path: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            vcf_paths=vcf_paths,
            output_vcf_path=output_vcf_path,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        vcf_paths: Sequence[str],
        output_vcf_path: str,
        **_: Any,
    ) -> str:
        """Merge the per-sample VCF paths into a cohort VCF and return the output path.

        Args:
            vcf_paths: Non-empty list or tuple of non-empty VCF file path strings.
            output_vcf_path: Non-empty path for the merged cohort VCF output file.

        Returns:
            Path string for the merged cohort VCF output file.

        Raises:
            TypeError: If vcf_paths is not list/tuple.
            ValueError: If vcf_paths is empty, contains empty strings, or output_vcf_path is empty.
        """
        if not isinstance(vcf_paths, (list, tuple)):
            raise TypeError("VCFMerger: vcf_paths must be list/tuple")
        if not vcf_paths:
            raise ValueError("VCFMerger: vcf_paths must be non-empty")
        for path in vcf_paths:
            if not isinstance(path, str) or not path:
                raise ValueError("VCFMerger: every vcf path must be a non-empty string")
        if not isinstance(output_vcf_path, str) or not output_vcf_path:
            raise ValueError("VCFMerger: output_vcf_path must be a non-empty string")
        cmd = ["bcftools", "merge", *list(vcf_paths), "-o", output_vcf_path]
        await _run_subprocess(cmd)
        return output_vcf_path
