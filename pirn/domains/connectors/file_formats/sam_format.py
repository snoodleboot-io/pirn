"""``SamFormat`` — Sequence Alignment/Map (SAM) text encoder/decoder.

SAM is the text-format companion to BAM/CRAM. Each record describes one
sequence alignment: read identifier, flag bitmask, reference contig and
position, mapping quality, CIGAR string, mate information, and the read
sequence and base qualities.

pirn uses ``pysam`` (htslib bindings) for both decode and encode. ``pysam``
exposes :class:`pysam.AlignmentFile` only against on-disk paths, so the
implementation round-trips through a temporary file.

Header handling: the constructor accepts an optional ``header_lines``
sequence (e.g. ``("@HD\\tVN:1.6", "@SQ\\tSN:chr1\\tLN:248956422")``).
When ``None``, a minimal header is inferred from the records — every
``rname`` referenced becomes an ``@SQ`` entry sized to fit the highest
``pos + len(seq)`` observed for that contig.

Security: pysam invokes htslib via C bindings. Treat untrusted SAM
payloads accordingly; pirn does not sandbox the parser.

Install: ``pip install pirn[genomics]``.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class SamFormat(BatchFileFormat):
    """Whole-file SAM (text) encoder/decoder."""

    def __init__(
        self,
        header_lines: Sequence[str] | None = None,
    ) -> None:
        if header_lines is not None:
            if isinstance(header_lines, (str, bytes)) or not isinstance(
                header_lines, Sequence
            ):
                raise TypeError(
                    "SamFormat: header_lines must be a sequence of "
                    f"strings, got {type(header_lines).__name__}"
                )
            for line in header_lines:
                if not isinstance(line, str) or not line:
                    raise ValueError(
                        "SamFormat: every header line must be a "
                        f"non-empty string, got {line!r}"
                    )
                if not line.startswith("@"):
                    raise ValueError(
                        "SamFormat: every header line must start with "
                        f"'@', got {line!r}"
                    )
        self._header_lines: tuple[str, ...] | None = (
            tuple(header_lines) if header_lines is not None else None
        )

    @property
    def name(self) -> str:
        return "sam"

    @property
    def header_lines(self) -> tuple[str, ...] | None:
        return self._header_lines

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        pysam = self._load_pysam()
        path = _write_tempfile(payload, suffix=".sam")
        try:
            handle = pysam.AlignmentFile(path, "r")
            try:
                records: list[Mapping[str, Any]] = []
                for alignment in handle:
                    records.append(_alignment_to_record(alignment, handle))
                return records
            finally:
                handle.close()
        finally:
            _safe_unlink(path)

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        pysam = self._load_pysam()
        materialised: list[Mapping[str, Any]] = list(records)
        header = _build_header(pysam, self._header_lines, materialised)
        path = _make_tempfile_path(suffix=".sam")
        try:
            handle = pysam.AlignmentFile(path, "w", header=header)
            try:
                for record in materialised:
                    alignment = _record_to_alignment(pysam, record, handle)
                    handle.write(alignment)
            finally:
                handle.close()
            with open(path, "rb") as fh:
                return fh.read()
        finally:
            _safe_unlink(path)

    @staticmethod
    def _load_pysam() -> Any:
        try:
            import pysam
        except ImportError as exc:
            raise ImportError(
                "SamFormat requires pysam. Install with "
                "`pip install pirn[genomics]`."
            ) from exc
        return pysam


# ---------------------------------------------------------------------------
# Module-level helpers (shared with BAM/CRAM via direct import).
# ---------------------------------------------------------------------------


def _write_tempfile(payload: bytes, suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
    except Exception:
        _safe_unlink(path)
        raise
    return path


def _make_tempfile_path(suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return path


def _safe_unlink(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def _alignment_to_record(
    alignment: Any, handle: Any
) -> Mapping[str, Any]:
    rname = (
        handle.get_reference_name(alignment.reference_id)
        if alignment.reference_id >= 0
        else "*"
    )
    rnext = (
        handle.get_reference_name(alignment.next_reference_id)
        if alignment.next_reference_id >= 0
        else "*"
    )
    if rnext is not None and rnext == rname and rname != "*":
        rnext = "="
    cigar = alignment.cigarstring or "*"
    seq = alignment.query_sequence or "*"
    qual = alignment.qual if alignment.qual is not None else "*"
    return {
        "qname": alignment.query_name or "*",
        "flag": int(alignment.flag),
        "rname": rname if rname is not None else "*",
        "pos": int(alignment.reference_start) + 1
        if alignment.reference_start is not None and alignment.reference_start >= 0
        else 0,
        "mapq": int(alignment.mapping_quality),
        "cigar": cigar,
        "rnext": rnext if rnext is not None else "*",
        "pnext": int(alignment.next_reference_start) + 1
        if alignment.next_reference_start is not None
        and alignment.next_reference_start >= 0
        else 0,
        "tlen": int(alignment.template_length),
        "seq": seq,
        "qual": qual,
    }


def _build_header(
    pysam: Any,
    explicit_lines: tuple[str, ...] | None,
    records: Sequence[Mapping[str, Any]],
) -> Any:
    if explicit_lines is not None:
        text = "\n".join(explicit_lines) + "\n"
        return _header_from_text(pysam, text)
    return _infer_header(pysam, records)


def _header_from_text(pysam: Any, text: str) -> Any:
    path = _make_tempfile_path(suffix=".sam")
    try:
        with open(path, "w") as fh:
            fh.write(text)
        handle = pysam.AlignmentFile(path, "r")
        try:
            return handle.header.to_dict()
        finally:
            handle.close()
    finally:
        _safe_unlink(path)


def _infer_header(
    pysam: Any, records: Sequence[Mapping[str, Any]]
) -> Any:
    contigs: dict[str, int] = {}
    order: list[str] = []
    for record in records:
        rname = record.get("rname")
        if not isinstance(rname, str) or rname in {"", "*"}:
            continue
        seq = record.get("seq")
        seq_len = len(seq) if isinstance(seq, str) and seq != "*" else 0
        pos = record.get("pos")
        pos_int = int(pos) if isinstance(pos, int) else 0
        upper = max(pos_int + seq_len, 1)
        if rname not in contigs:
            order.append(rname)
            contigs[rname] = upper
        else:
            if upper > contigs[rname]:
                contigs[rname] = upper
    if not order:
        order = ["chr1"]
        contigs = {"chr1": 1}
    sq_entries = [
        {"SN": name, "LN": max(contigs[name], 1)} for name in order
    ]
    return {"HD": {"VN": "1.6"}, "SQ": sq_entries}


def _record_to_alignment(
    pysam: Any, record: Mapping[str, Any], handle: Any
) -> Any:
    _validate_record(record)
    alignment = pysam.AlignedSegment(handle.header)
    alignment.query_name = str(record["qname"])
    alignment.flag = int(record["flag"])
    rname = str(record["rname"])
    if rname not in {"", "*"}:
        alignment.reference_id = handle.header.get_tid(rname)
    else:
        alignment.reference_id = -1
    pos = int(record["pos"])
    alignment.reference_start = pos - 1 if pos > 0 else -1
    alignment.mapping_quality = int(record["mapq"])
    cigar = str(record["cigar"])
    alignment.cigarstring = cigar if cigar != "*" else None
    rnext = str(record["rnext"])
    if rnext == "=":
        alignment.next_reference_id = alignment.reference_id
    elif rnext not in {"", "*"}:
        alignment.next_reference_id = handle.header.get_tid(rnext)
    else:
        alignment.next_reference_id = -1
    pnext = int(record["pnext"])
    alignment.next_reference_start = pnext - 1 if pnext > 0 else -1
    alignment.template_length = int(record["tlen"])
    seq = str(record["seq"])
    qual = str(record["qual"])
    if seq == "*":
        alignment.query_sequence = None
    else:
        alignment.query_sequence = seq
        if qual != "*":
            alignment.query_qualities = pysam.qualitystring_to_array(qual)
    return alignment


def _validate_record(record: Mapping[str, Any]) -> None:
    required = (
        "qname",
        "flag",
        "rname",
        "pos",
        "mapq",
        "cigar",
        "rnext",
        "pnext",
        "tlen",
        "seq",
        "qual",
    )
    missing = [field for field in required if field not in record]
    if missing:
        raise ValueError(
            "SamFormat: record missing required fields "
            f"{missing}; got keys {list(record.keys())}"
        )
