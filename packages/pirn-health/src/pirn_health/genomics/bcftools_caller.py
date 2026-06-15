"""``BCFtoolsCaller`` — bcftools-based variant caller.

Production version invokes ``bcftools mpileup | bcftools call`` via
subprocess; this stub validates inputs and returns a VCF path.

Algorithm:
    1. Receive bam_path, reference_path, and output_vcf_path strings.
    2. Validate that all paths are non-empty strings.
    3. Run bcftools mpileup followed by bcftools call on the BAM.
    4. Write the VCF output to output_vcf_path.
    5. Return the output VCF path.


References:
    - bcftools: https://samtools.github.io/bcftools/bcftools.html
    - Li (2011) A statistical framework for SNP calling, mutation discovery, and population genetics inference.
"""

from __future__ import annotations

import asyncio
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


class BCFtoolsCaller(Knot):
    """Call variants with bcftools and return the VCF path."""

    def __init__(
        self,
        *,
        bam_path: Knot | str,
        reference_path: Knot | str,
        output_vcf_path: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            bam_path=bam_path,
            reference_path=reference_path,
            output_vcf_path=output_vcf_path,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        bam_path: str,
        reference_path: str,
        output_vcf_path: str,
        **_: Any,
    ) -> str:
        """Run bcftools variant calling on the BAM against the reference and return the output VCF path.

        Args:
            bam_path: Non-empty path to the input BAM file.
            reference_path: Non-empty path to the reference FASTA file.
            output_vcf_path: Non-empty path for the output VCF file.

        Returns:
            The output VCF path.

        Raises:
            TypeError: If any path is not a string.
            ValueError: If any path is empty.
        """
        for label, value in (
            ("bam_path", bam_path),
            ("reference_path", reference_path),
            ("output_vcf_path", output_vcf_path),
        ):
            if not isinstance(value, str):
                raise TypeError(f"BCFtoolsCaller: {label} must be a string")
            if not value:
                raise ValueError(f"BCFtoolsCaller: {label} must be non-empty")
        mpileup_proc = await asyncio.create_subprocess_exec(
            "bcftools",
            "mpileup",
            "-f",
            reference_path,
            bam_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        call_proc = await asyncio.create_subprocess_exec(
            "bcftools",
            "call",
            "-mv",
            "-o",
            output_vcf_path,
            stdin=mpileup_proc.stdout,  # type: ignore[arg-type]
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        __, call_stderr = await call_proc.communicate()
        await mpileup_proc.wait()
        if mpileup_proc.returncode != 0:
            raise RuntimeError("bcftools mpileup failed")
        if call_proc.returncode != 0:
            raise RuntimeError(f"bcftools call failed: {call_stderr.decode()}")
        return output_vcf_path
