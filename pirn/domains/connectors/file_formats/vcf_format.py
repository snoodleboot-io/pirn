"""``VcfFormat`` — Variant Call Format (text) encoder/decoder.

VCF is a tab-delimited text format used in genomics for variant calls.
The text dialect is straightforward enough to parse with stdlib —
``##`` lines are metadata, ``#CHROM`` is the column header, and the
remaining rows are tab-delimited variant records.

The optional ``pysam`` package (declared via ``pirn[genomics]``) is the
canonical reference implementation; users requiring strict spec
compliance, indexed access, or BGZF-aware streaming should reach for
:class:`pirn.domains.connectors.file_formats.bcf_format.BcfFormat` or a
dedicated reader. This class targets the common ingestion use case of
parsing well-formed VCF text into pirn record dicts.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn.domains.connectors.file_formats.streaming_file_format import (
    StreamingFileFormat,
)


class VcfFormat(StreamingFileFormat):
    """Streaming VCF text encoder/decoder.

    Args:
        encoding: Text encoding for the byte stream. Defaults to
            ``"utf-8"``.
        fileformat: Value emitted for the ``##fileformat=`` header on
            write. Defaults to ``"VCFv4.3"``.
    """

    def __init__(
        self,
        encoding: str = "utf-8",
        fileformat: str = "VCFv4.3",
    ) -> None:
        if not isinstance(encoding, str):
            raise TypeError("VcfFormat: encoding must be str")
        if not encoding:
            raise ValueError("VcfFormat: encoding must be non-empty")
        if not isinstance(fileformat, str):
            raise TypeError("VcfFormat: fileformat must be str")
        if not fileformat:
            raise ValueError("VcfFormat: fileformat must be non-empty")
        self._encoding = encoding
        self._fileformat = fileformat

    @property
    def name(self) -> str:
        return "vcf"

    @property
    def encoding(self) -> str:
        return self._encoding

    @property
    def fileformat(self) -> str:
        return self._fileformat

    async def read(
        self, body: AsyncIterator[bytes]
    ) -> AsyncIterator[Mapping[str, Any]]:
        encoding = self._encoding

        async def _iter() -> AsyncIterator[Mapping[str, Any]]:
            buffered = bytearray()
            saw_column_header = False

            async for chunk in body:
                buffered.extend(chunk)
                for line in VcfFormat._drain_lines(buffered, encoding, final=False):
                    if line.startswith("##"):
                        continue
                    if line.startswith("#"):
                        saw_column_header = True
                        continue
                    if not line:
                        continue
                    yield VcfFormat._parse_data_row(line)

            for line in VcfFormat._drain_lines(buffered, encoding, final=True):
                if line.startswith("##"):
                    continue
                if line.startswith("#"):
                    saw_column_header = True
                    continue
                if not line:
                    continue
                yield VcfFormat._parse_data_row(line)

            # No-op: presence of column header isn't required for parsing
            # data rows but we capture the flag for future strictness.
            _ = saw_column_header

        return _iter()

    async def write(
        self, records: AsyncIterator[Mapping[str, Any]]
    ) -> AsyncIterator[bytes]:
        encoding = self._encoding
        fileformat = self._fileformat

        async def _iter() -> AsyncIterator[bytes]:
            header = (
                f"##fileformat={fileformat}\n"
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
            )
            yield header.encode(encoding)
            async for record in records:
                yield VcfFormat._serialize_data_row(record).encode(encoding)

        return _iter()

    @staticmethod
    def _drain_lines(buffered: bytearray, encoding: str, final: bool) -> list[str]:
        lines: list[str] = []
        while True:
            newline_index = buffered.find(b"\n")
            if newline_index == -1:
                break
            raw_line = bytes(buffered[:newline_index])
            del buffered[: newline_index + 1]
            lines.append(raw_line.decode(encoding).rstrip("\r"))
        if final and buffered:
            lines.append(bytes(buffered).decode(encoding).rstrip("\r"))
            buffered.clear()
        return lines

    @staticmethod
    def _parse_data_row(line: str) -> Mapping[str, Any]:
        fields = line.split("\t")
        if len(fields) < 8:
            raise ValueError(
                "VcfFormat: data row must have at least 8 tab-separated "
                f"fields (CHROM..INFO); got {len(fields)}"
            )
        chrom, pos_text, identifier, ref, alt, qual_text, filt, info_text = (
            fields[:8]
        )
        try:
            pos = int(pos_text)
        except ValueError as exc:
            raise ValueError(
                f"VcfFormat: POS must be integer, got {pos_text!r}"
            ) from exc
        qual: float | None
        if qual_text == "." or qual_text == "":
            qual = None
        else:
            try:
                qual = float(qual_text)
            except ValueError as exc:
                raise ValueError(
                    f"VcfFormat: QUAL must be float or '.', got {qual_text!r}"
                ) from exc
        info = VcfFormat._parse_info_field(info_text)
        return {
            "chrom": chrom,
            "pos": pos,
            "id": identifier,
            "ref": ref,
            "alt": alt,
            "qual": qual,
            "filter": filt,
            "info": info,
        }

    @staticmethod
    def _parse_info_field(info_text: str) -> Mapping[str, Any]:
        if info_text == "" or info_text == ".":
            return {}
        info: dict[str, Any] = {}
        for entry in info_text.split(";"):
            if not entry:
                continue
            if "=" in entry:
                key, value = entry.split("=", 1)
                info[key] = value
            else:
                info[entry] = True
        return info

    @staticmethod
    def _serialize_data_row(record: Mapping[str, Any]) -> str:
        chrom = record.get("chrom")
        if not isinstance(chrom, str) or not chrom:
            raise ValueError(
                "VcfFormat: 'chrom' must be a non-empty string"
            )
        pos = record.get("pos")
        if not isinstance(pos, int) or isinstance(pos, bool):
            raise TypeError("VcfFormat: 'pos' must be int")
        identifier = record.get("id", ".")
        if identifier is None:
            identifier = "."
        if not isinstance(identifier, str):
            raise TypeError("VcfFormat: 'id' must be str")
        ref = record.get("ref")
        if not isinstance(ref, str) or not ref:
            raise ValueError(
                "VcfFormat: 'ref' must be a non-empty string"
            )
        alt = record.get("alt")
        if not isinstance(alt, str) or not alt:
            raise ValueError(
                "VcfFormat: 'alt' must be a non-empty string"
            )
        qual = record.get("qual")
        if qual is None:
            qual_text = "."
        elif isinstance(qual, (int, float)) and not isinstance(qual, bool):
            qual_text = f"{float(qual):g}"
        else:
            raise TypeError(
                "VcfFormat: 'qual' must be float, int, or None"
            )
        filt = record.get("filter", ".")
        if filt is None:
            filt = "."
        if not isinstance(filt, str):
            raise TypeError("VcfFormat: 'filter' must be str")
        info = record.get("info", {})
        if info is None:
            info = {}
        if not isinstance(info, Mapping):
            raise TypeError(
                "VcfFormat: 'info' must be a mapping (dict-like)"
            )
        info_text = VcfFormat._serialize_info_field(info)
        return (
            f"{chrom}\t{pos}\t{identifier}\t{ref}\t{alt}\t"
            f"{qual_text}\t{filt}\t{info_text}\n"
        )

    @staticmethod
    def _serialize_info_field(info: Mapping[str, Any]) -> str:
        if not info:
            return "."
        parts: list[str] = []
        for key, value in info.items():
            if not isinstance(key, str) or not key:
                raise ValueError(
                    "VcfFormat: every INFO key must be a non-empty string"
                )
            if value is True:
                parts.append(key)
            elif value is False or value is None:
                continue
            else:
                parts.append(f"{key}={value}")
        if not parts:
            return "."
        return ";".join(parts)
