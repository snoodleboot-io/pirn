# pyright: reportUnnecessaryIsInstance=false
# runtime-bound inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``BamFormat`` — Binary Alignment/Map (BAM) encoder/decoder.

BAM is the BGZF-compressed binary form of SAM. Same record structure as
:class:`SamFormat` (``qname``, ``flag``, ``rname``, ``pos``, ``mapq``,
``cigar``, ``rnext``, ``pnext``, ``tlen``, ``seq``, ``qual``); the wire
format is binary. pirn uses ``pysam`` for both directions and round-trips
through a temporary ``.bam`` file because ``pysam.AlignmentFile`` requires
on-disk paths.

Header handling: the constructor accepts an optional ``header_lines``
sequence (e.g. ``("@HD\\tVN:1.6", "@SQ\\tSN:chr1\\tLN:248956422")``).
When ``None``, a minimal header is inferred from the records (see
:meth:`pirn.connectors.file_formats.sam_utils.SamUtils.infer_header`).

Security: pysam invokes htslib via C bindings. Treat untrusted BAM
payloads accordingly; pirn does not sandbox the parser.

Install: ``pip install "pirn-health[genomics]"``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.file_formats.sam_utils import SamUtils
from pirn.core.optional_dependency import OptionalDependency


class BamFormat(BatchFileFormat):
    """Whole-file BAM (binary) encoder/decoder."""

    def __init__(
        self,
        header_lines: Sequence[str] | None = None,
    ) -> None:
        if header_lines is not None:
            if isinstance(header_lines, (str, bytes)) or not isinstance(header_lines, Sequence):
                raise TypeError(
                    "BamFormat: header_lines must be a sequence of "
                    f"strings, got {type(header_lines).__name__}"
                )
            for line in header_lines:
                if not isinstance(line, str) or not line:
                    raise ValueError(
                        f"BamFormat: every header line must be a non-empty string, got {line!r}"
                    )
                if not line.startswith("@"):
                    raise ValueError(
                        f"BamFormat: every header line must start with '@', got {line!r}"
                    )
        self._header_lines: tuple[str, ...] | None = (
            tuple(header_lines) if header_lines is not None else None
        )

    @property
    def name(self) -> str:
        return "bam"

    @property
    def header_lines(self) -> tuple[str, ...] | None:
        return self._header_lines

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        pysam = OptionalDependency.require("pysam", extra="genomics", package="pirn-health")
        path = SamUtils.write_tempfile(payload, suffix=".bam")
        try:
            handle = pysam.AlignmentFile(path, "rb")
            try:
                records: list[Mapping[str, Any]] = []
                for alignment in handle:
                    records.append(SamUtils.alignment_to_record(alignment, handle))
                return records
            finally:
                handle.close()
        finally:
            SamUtils.safe_unlink(path)

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        pysam = OptionalDependency.require("pysam", extra="genomics", package="pirn-health")
        materialised: list[Mapping[str, Any]] = list(records)
        header = SamUtils.build_header(pysam, self._header_lines, materialised)
        path = SamUtils.make_tempfile_path(suffix=".bam")
        try:
            handle = pysam.AlignmentFile(path, "wb", header=header)
            try:
                for record in materialised:
                    alignment = SamUtils.record_to_alignment(pysam, record, handle)
                    handle.write(alignment)
            finally:
                handle.close()
            with open(path, "rb") as fh:
                return fh.read()
        finally:
            SamUtils.safe_unlink(path)
