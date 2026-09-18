"""Unit tests for :class:`BCFtoolsCaller`."""

from __future__ import annotations

import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from pirn.core.knot_config import KnotConfig

from pirn_health.genomics.bcftools_caller import BCFtoolsCaller

_CFG = KnotConfig(id="b")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> BCFtoolsCaller:
        return BCFtoolsCaller(
            bam_path="in.bam",
            reference_path="ref.fa",
            output_vcf_path="out.vcf",
            _config=_CFG,
        )

    async def test_rejects_non_string_bam(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "bam_path"):
            await knot.process(bam_path=42, reference_path="ref", output_vcf_path="out")

    async def test_rejects_empty_bam(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(bam_path="", reference_path="ref", output_vcf_path="out")

    async def test_returns_vcf_path(self) -> None:
        knot = self._make_knot()
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.wait = AsyncMock(return_value=0)
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            out = await knot.process(
                bam_path="in.bam", reference_path="ref.fa", output_vcf_path="out.vcf"
            )
        assert out == "out.vcf"

    async def test_pipes_mpileup_stdout_into_call_stdin(self) -> None:
        knot = self._make_knot()
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        exec_mock = AsyncMock(return_value=mock_proc)
        with patch("asyncio.create_subprocess_exec", exec_mock):
            await knot.process(
                bam_path="in.bam", reference_path="ref.fa", output_vcf_path="out.vcf"
            )
        mpileup_call, call_call = exec_mock.await_args_list
        write_fd = mpileup_call.kwargs["stdout"]
        read_fd = call_call.kwargs["stdin"]
        assert isinstance(write_fd, int)
        assert isinstance(read_fd, int)
        assert write_fd != read_fd
        # The parent closed both pipe ends after spawning the children.
        with self.assertRaises(OSError):
            os.fstat(write_fd)
        with self.assertRaises(OSError):
            os.fstat(read_fd)

    async def test_raises_when_mpileup_fails(self) -> None:
        knot = self._make_knot()
        mpileup_proc = MagicMock()
        mpileup_proc.returncode = 1
        mpileup_proc.communicate = AsyncMock(return_value=(b"", b"boom"))
        call_proc = MagicMock()
        call_proc.returncode = 0
        call_proc.communicate = AsyncMock(return_value=(b"", b""))
        exec_mock = AsyncMock(side_effect=[mpileup_proc, call_proc])
        with patch("asyncio.create_subprocess_exec", exec_mock):
            with self.assertRaisesRegex(RuntimeError, "mpileup failed"):
                await knot.process(
                    bam_path="in.bam", reference_path="ref.fa", output_vcf_path="out.vcf"
                )

    async def test_raises_when_call_fails(self) -> None:
        knot = self._make_knot()
        mpileup_proc = MagicMock()
        mpileup_proc.returncode = 0
        mpileup_proc.communicate = AsyncMock(return_value=(b"", b""))
        call_proc = MagicMock()
        call_proc.returncode = 2
        call_proc.communicate = AsyncMock(return_value=(b"", b"bad call"))
        exec_mock = AsyncMock(side_effect=[mpileup_proc, call_proc])
        with patch("asyncio.create_subprocess_exec", exec_mock):
            with self.assertRaisesRegex(RuntimeError, "bcftools call failed: bad call"):
                await knot.process(
                    bam_path="in.bam", reference_path="ref.fa", output_vcf_path="out.vcf"
                )
