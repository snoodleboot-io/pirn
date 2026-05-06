"""``CramFormat`` — Compressed Reference-aligned/Map (CRAM) encoder/decoder.

CRAM is a reference-based compression of BAM: instead of writing the
read sequence verbatim, only differences from a reference FASTA are
stored. That makes CRAM substantially smaller than BAM but couples
decoding to the same reference. Without it, sequence reconstruction is
lossy (best-effort) — pirn requires a reference for writes and will
honour one for reads when supplied.

Record shape matches :class:`SamFormat`/:class:`BamFormat` (``qname``,
``flag``, ``rname``, ``pos``, ``mapq``, ``cigar``, ``rnext``, ``pnext``,
``tlen``, ``seq``, ``qual``).

Security: pysam invokes htslib via C bindings. Treat untrusted CRAM
payloads accordingly; pirn does not sandbox the parser.

Install: ``pip install pirn[genomics]``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from pirn.domains.connectors.file_formats._sam_utils import _SamUtils
from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class CramFormat(BatchFileFormat):
    """Whole-file CRAM encoder/decoder."""

    def __init__(
        self,
        reference_fasta: str | None = None,
        header_lines: Sequence[str] | None = None,
    ) -> None:
        if reference_fasta is not None and (
            not isinstance(reference_fasta, str) or not reference_fasta
        ):
            raise ValueError(
                "CramFormat: reference_fasta must be a non-empty string "
                "or None"
            )
        if header_lines is not None:
            if isinstance(header_lines, (str, bytes)) or not isinstance(
                header_lines, Sequence
            ):
                raise TypeError(
                    "CramFormat: header_lines must be a sequence of "
                    f"strings, got {type(header_lines).__name__}"
                )
            for line in header_lines:
                if not isinstance(line, str) or not line:
                    raise ValueError(
                        "CramFormat: every header line must be a "
                        f"non-empty string, got {line!r}"
                    )
                if not line.startswith("@"):
                    raise ValueError(
                        "CramFormat: every header line must start with "
                        f"'@', got {line!r}"
                    )
        self._reference_fasta = reference_fasta
        self._header_lines: tuple[str, ...] | None = (
            tuple(header_lines) if header_lines is not None else None
        )

    @property
    def name(self) -> str:
        return "cram"

    @property
    def reference_fasta(self) -> str | None:
        return self._reference_fasta

    @property
    def header_lines(self) -> tuple[str, ...] | None:
        return self._header_lines

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        pysam = self._load_pysam()
        path = _SamUtils.write_tempfile(payload, suffix=".cram")
        try:
            handle = pysam.AlignmentFile(
                path,
                "rc",
                reference_filename=self._reference_fasta,
            )
            try:
                records: list[Mapping[str, Any]] = []
                for alignment in handle:
                    records.append(_SamUtils.alignment_to_record(alignment, handle))
                return records
            finally:
                handle.close()
        finally:
            _SamUtils.safe_unlink(path)

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        if self._reference_fasta is None:
            raise ValueError(
                "CramFormat: reference_fasta is required for write"
            )
        pysam = self._load_pysam()
        materialised: list[Mapping[str, Any]] = list(records)
        header = _SamUtils.build_header(pysam, self._header_lines, materialised)
        path = _SamUtils.make_tempfile_path(suffix=".cram")
        try:
            handle = pysam.AlignmentFile(
                path,
                "wc",
                header=header,
                reference_filename=self._reference_fasta,
            )
            try:
                for record in materialised:
                    alignment = _SamUtils.record_to_alignment(pysam, record, handle)
                    handle.write(alignment)
            finally:
                handle.close()
            with open(path, "rb") as fh:
                return fh.read()
        finally:
            _SamUtils.safe_unlink(path)

    @staticmethod
    def _load_pysam() -> Any:
        try:
            import pysam
        except ImportError as exc:
            raise ImportError(
                "CramFormat requires pysam. Install with "
                "`pip install pirn[genomics]`."
            ) from exc
        return pysam
