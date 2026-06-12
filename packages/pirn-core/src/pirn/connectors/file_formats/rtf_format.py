"""``RtfFormat`` — Rich Text Format encoder/decoder.

Reads use ``striprtf`` to extract plain text from an RTF document.
Writes emit a minimal RTF skeleton wrapping the concatenated text from
each record. Round-trip is text-only — fonts, colors, tables, and
embedded objects are not preserved.

Records have shape ``{"text": str}``. RTF doesn't have natural record
boundaries, so reads always yield a single record with the entire
extracted text.

Install: ``pip install pirn[rtf]``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class RtfFormat(BatchFileFormat):
    """Whole-file RTF encoder/decoder."""

    def __init__(self, encoding: str = "utf-8") -> None:
        if not isinstance(encoding, str):
            raise TypeError("RtfFormat: encoding must be str")
        if not encoding:
            raise ValueError("RtfFormat: encoding must be non-empty")
        self._encoding = encoding

    @property
    def name(self) -> str:
        return "rtf"

    @property
    def encoding(self) -> str:
        return self._encoding

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        if not payload:
            return []
        rtf_to_text = self._load_striprtf()
        # RTF is ASCII with escapes; decode permissively then strip.
        rtf_source = payload.decode(self._encoding, errors="replace")
        plain = rtf_to_text(rtf_source)
        return [{"text": plain}]

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        materialised = list(records)
        if not materialised:
            return b""
        body_parts: list[str] = []
        for record in materialised:
            text = self._extract_text(record)
            body_parts.append(self._escape_rtf(text))
        body = r" \par ".join(body_parts)
        document = (
            r"{\rtf1\ansi\deff0"
            r"{\fonttbl{\f0 Times New Roman;}}"
            r"\f0\fs24 "
            f"{body}"
            "}"
        )
        return document.encode(self._encoding)

    @staticmethod
    def _escape_rtf(text: str) -> str:
        # Escape RTF metacharacters and convert non-ASCII to \uN escapes.
        out: list[str] = []
        for ch in text:
            if ch == "\\":
                out.append(r"\\")
            elif ch == "{":
                out.append(r"\{")
            elif ch == "}":
                out.append(r"\}")
            elif ch == "\n":
                out.append(r"\par ")
            elif ch == "\r":
                continue
            elif ch == "\t":
                out.append(r"\tab ")
            elif ord(ch) < 128:
                out.append(ch)
            else:
                code = ord(ch)
                if code > 32767:
                    code -= 65536
                out.append(f"\\u{code}?")
        return "".join(out)

    @staticmethod
    def _extract_text(record: Mapping[str, Any]) -> str:
        if "text" not in record:
            raise ValueError("RtfFormat: record missing required 'text' key")
        text = record["text"]
        if not isinstance(text, str):
            raise TypeError(
                f"RtfFormat: record 'text' value must be str, got {type(text).__name__}"
            )
        return text

    @staticmethod
    def _load_striprtf() -> Any:
        try:
            from striprtf.striprtf import rtf_to_text
        except ImportError as exc:
            raise ImportError(
                "RtfFormat requires striprtf. Install with `pip install pirn[rtf]`."
            ) from exc
        return rtf_to_text
