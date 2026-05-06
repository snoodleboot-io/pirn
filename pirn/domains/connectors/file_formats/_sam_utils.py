"""Shared SAM/BAM/CRAM utility helpers.

These helpers are stateless and used by
:class:`SamFormat`, :class:`BamFormat`, and :class:`CramFormat`.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping, Sequence
from typing import Any


class _SamUtils:
    """Namespace for SAM/BAM/CRAM stateless utilities."""

    @staticmethod
    def write_tempfile(payload: bytes, suffix: str) -> str:
        fd, path = tempfile.mkstemp(suffix=suffix)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(payload)
        except Exception:
            _SamUtils.safe_unlink(path)
            raise
        return path

    @staticmethod
    def make_tempfile_path(suffix: str) -> str:
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        return path

    @staticmethod
    def safe_unlink(path: str) -> None:
        try:
            os.unlink(path)
        except OSError:
            pass

    @staticmethod
    def alignment_to_record(alignment: Any, handle: Any) -> Mapping[str, Any]:
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
            if alignment.next_reference_start is not None and alignment.next_reference_start >= 0
            else 0,
            "tlen": int(alignment.template_length),
            "seq": seq,
            "qual": qual,
        }

    @staticmethod
    def build_header(
        pysam: Any,
        explicit_lines: tuple[str, ...] | None,
        records: Sequence[Mapping[str, Any]],
    ) -> Any:
        if explicit_lines is not None:
            text = "\n".join(explicit_lines) + "\n"
            return _SamUtils.header_from_text(pysam, text)
        return _SamUtils.infer_header(pysam, records)

    @staticmethod
    def header_from_text(pysam: Any, text: str) -> Any:
        path = _SamUtils.make_tempfile_path(suffix=".sam")
        try:
            with open(path, "w") as fh:
                fh.write(text)
            handle = pysam.AlignmentFile(path, "r")
            try:
                return handle.header.to_dict()
            finally:
                handle.close()
        finally:
            _SamUtils.safe_unlink(path)

    @staticmethod
    def infer_header(pysam: Any, records: Sequence[Mapping[str, Any]]) -> Any:
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
        sq_entries = [{"SN": name, "LN": max(contigs[name], 1)} for name in order]
        return {"HD": {"VN": "1.6"}, "SQ": sq_entries}

    @staticmethod
    def record_to_alignment(pysam: Any, record: Mapping[str, Any], handle: Any) -> Any:
        _SamUtils.validate_record(record)
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

    @staticmethod
    def validate_record(record: Mapping[str, Any]) -> None:
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
