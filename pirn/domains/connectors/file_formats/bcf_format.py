"""``BcfFormat`` — Binary Variant Call Format encoder/decoder.

BCF is the binary, BGZF-compressed companion of VCF. Decoding requires
``pysam``, which wraps htslib and only operates against an on-disk path
(it cannot stream from a Python file-like object). We therefore expose
BCF through :class:`BatchFileFormat`: ``read`` buffers the byte stream,
spills it to a temp file, and then iterates ``pysam.VariantFile``.

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


class BcfFormat(BatchFileFormat):
    """Whole-file BCF encoder/decoder backed by ``pysam``.

    Args:
        header_lines: Optional sequence of ``##``-prefixed header lines
            used when encoding. When ``None``, a minimal header is
            inferred from the first record's ``info`` keys.
    """

    def __init__(
        self,
        header_lines: Sequence[str] | None = None,
    ) -> None:
        if header_lines is not None:
            if isinstance(header_lines, (str, bytes)):
                raise TypeError(
                    "BcfFormat: header_lines must be a sequence of "
                    "strings, not str/bytes"
                )
            if not isinstance(header_lines, Sequence):
                raise TypeError(
                    "BcfFormat: header_lines must be a sequence of "
                    f"strings, got {type(header_lines).__name__}"
                )
            for line in header_lines:
                if not isinstance(line, str) or not line:
                    raise ValueError(
                        "BcfFormat: every header line must be a "
                        f"non-empty string, got {line!r}"
                    )
            self._header_lines: tuple[str, ...] | None = tuple(header_lines)
        else:
            self._header_lines = None

    @property
    def name(self) -> str:
        return "bcf"

    @property
    def header_lines(self) -> tuple[str, ...] | None:
        return self._header_lines

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        pysam = self._load_pysam()
        with tempfile.NamedTemporaryFile(
            suffix=".bcf", delete=False
        ) as tmp:
            tmp.write(payload)
            tmp_path = tmp.name
        try:
            records: list[Mapping[str, Any]] = []
            variant_file = pysam.VariantFile(tmp_path, "rb")
            try:
                for variant in variant_file:
                    records.append(_record_from_variant(variant))
            finally:
                variant_file.close()
            return records
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        pysam = self._load_pysam()
        materialised: list[Mapping[str, Any]] = list(records)
        if not materialised and self._header_lines is None:
            raise ValueError(
                "BcfFormat: cannot infer header from an empty record "
                "set; pass header_lines=... to the constructor"
            )
        header = self._build_header(pysam, materialised)
        with tempfile.NamedTemporaryFile(
            suffix=".bcf", delete=False
        ) as tmp:
            tmp_path = tmp.name
        try:
            writer = pysam.VariantFile(tmp_path, "wb", header=header)
            try:
                for record in materialised:
                    writer.write(_variant_from_record(writer, record))
            finally:
                writer.close()
            with open(tmp_path, "rb") as handle:
                return handle.read()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _build_header(
        self,
        pysam: Any,
        records: Sequence[Mapping[str, Any]],
    ) -> Any:
        header = pysam.VariantHeader()
        seen_contigs: set[str] = set()
        if self._header_lines is not None:
            for line in self._header_lines:
                header.add_line(line)
                if line.startswith("##contig=<ID="):
                    contig_id = line.split("ID=", 1)[1].split(",", 1)[0]
                    contig_id = contig_id.rstrip(">")
                    seen_contigs.add(contig_id)
            for record in records:
                chrom = record.get("chrom")
                if isinstance(chrom, str) and chrom not in seen_contigs:
                    header.add_line(f"##contig=<ID={chrom}>")
                    seen_contigs.add(chrom)
            return header
        # Inferred minimal header.
        info_keys: list[str] = []
        for record in records:
            info = record.get("info", {})
            if isinstance(info, Mapping):
                for key in info.keys():
                    if isinstance(key, str) and key not in info_keys:
                        info_keys.append(key)
        for key in info_keys:
            header.add_line(
                f"##INFO=<ID={key},Number=1,Type=String,"
                f'Description="{key}">'
            )
        for record in records:
            chrom = record.get("chrom")
            if isinstance(chrom, str) and chrom not in seen_contigs:
                header.add_line(f"##contig=<ID={chrom}>")
                seen_contigs.add(chrom)
        return header

    @staticmethod
    def _load_pysam() -> Any:
        try:
            import pysam
        except ImportError as exc:
            raise ImportError(
                "BcfFormat requires pysam. Install with "
                "`pip install pirn[genomics]`."
            ) from exc
        return pysam


def _record_from_variant(variant: Any) -> Mapping[str, Any]:
    qual: float | None
    if variant.qual is None:
        qual = None
    else:
        qual = float(variant.qual)
    info: dict[str, Any] = {}
    for key, value in variant.info.items():
        if isinstance(value, tuple):
            info[key] = ",".join(str(item) for item in value)
        elif value is None:
            continue
        elif isinstance(value, bool):
            info[key] = value
        else:
            info[key] = str(value)
    if variant.alts is None:
        alt = ""
    else:
        alt = ",".join(variant.alts)
    if variant.filter.keys():
        filter_value = ";".join(variant.filter.keys())
    else:
        filter_value = "."
    return {
        "chrom": variant.chrom,
        "pos": variant.pos,
        "id": variant.id if variant.id is not None else ".",
        "ref": variant.ref if variant.ref is not None else "",
        "alt": alt,
        "qual": qual,
        "filter": filter_value,
        "info": info,
    }


def _variant_from_record(writer: Any, record: Mapping[str, Any]) -> Any:
    chrom = record.get("chrom")
    pos = record.get("pos")
    ref = record.get("ref")
    alt = record.get("alt")
    if not isinstance(chrom, str) or not chrom:
        raise ValueError("BcfFormat: 'chrom' must be a non-empty string")
    if not isinstance(pos, int) or isinstance(pos, bool):
        raise TypeError("BcfFormat: 'pos' must be int")
    if not isinstance(ref, str) or not ref:
        raise ValueError("BcfFormat: 'ref' must be a non-empty string")
    if not isinstance(alt, str) or not alt:
        raise ValueError("BcfFormat: 'alt' must be a non-empty string")
    alts = tuple(alt.split(","))
    new_record = writer.new_record()
    new_record.chrom = chrom
    new_record.pos = pos
    record_id = record.get("id", ".")
    if record_id is not None and record_id != ".":
        new_record.id = record_id
    new_record.ref = ref
    new_record.alts = alts
    qual = record.get("qual")
    if qual is not None:
        if not isinstance(qual, (int, float)) or isinstance(qual, bool):
            raise TypeError(
                "BcfFormat: 'qual' must be float, int, or None"
            )
        new_record.qual = float(qual)
    filt = record.get("filter")
    if isinstance(filt, str) and filt and filt != ".":
        for token in filt.split(";"):
            if token:
                new_record.filter.add(token)
    info = record.get("info") or {}
    if not isinstance(info, Mapping):
        raise TypeError("BcfFormat: 'info' must be a mapping")
    for key, value in info.items():
        if value is None or value is False:
            continue
        new_record.info[key] = value
    return new_record
