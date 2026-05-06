"""``FastqFormat`` — FASTQ sequence + quality encoder/decoder.

FASTQ is a simple text format used in bioinformatics. Each record is
exactly four lines:

* ``@{seq_id} {description}`` — header (``@`` prefix)
* sequence line
* ``+`` (optionally followed by the seq_id) — separator
* quality string (same length as the sequence)

Stdlib parsing is sufficient here. ``pyfaidx`` is an *optional*
dependency for indexed random-access reads (declared via
``pirn[genomics]``); it is not required by this format's streaming
encode/decode path.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn.domains.connectors.file_formats.streaming_file_format import (
    StreamingFileFormat,
)


class FastqFormat(StreamingFileFormat):
    """FASTQ file format implemented with stdlib parsing.

    Args:
        encoding: Text encoding for the byte stream. Defaults to
            ``"utf-8"``.
    """

    def __init__(self, encoding: str = "utf-8") -> None:
        if not isinstance(encoding, str):
            raise TypeError("FastqFormat: encoding must be str")
        if not encoding:
            raise ValueError("FastqFormat: encoding must be non-empty")
        self._encoding = encoding

    @property
    def name(self) -> str:
        return "fastq"

    @property
    def encoding(self) -> str:
        return self._encoding

    async def read(
        self, body: AsyncIterator[bytes]
    ) -> AsyncIterator[Mapping[str, Any]]:
        encoding = self._encoding

        async def _iter() -> AsyncIterator[Mapping[str, Any]]:
            buffered = bytearray()
            pending: list[str] = []

            async for chunk in body:
                buffered.extend(chunk)
                pending.extend(FastqFormat._drain_lines(buffered, encoding, final=False))
                while len(pending) >= 4:
                    record = FastqFormat._build_record(pending[:4])
                    del pending[:4]
                    yield record

            pending.extend(FastqFormat._drain_lines(buffered, encoding, final=True))
            while len(pending) >= 4:
                record = FastqFormat._build_record(pending[:4])
                del pending[:4]
                yield record
            if pending:
                raise ValueError(
                    "FastqFormat: trailing data does not form a "
                    f"complete 4-line record (got {len(pending)} lines)"
                )

        return _iter()

    async def write(
        self, records: AsyncIterator[Mapping[str, Any]]
    ) -> AsyncIterator[bytes]:
        encoding = self._encoding

        async def _iter() -> AsyncIterator[bytes]:
            async for record in records:
                seq_id = record.get("seq_id")
                if not isinstance(seq_id, str) or not seq_id:
                    raise ValueError(
                        "FastqFormat: each record must have a non-empty "
                        "string 'seq_id'"
                    )
                if any(ch.isspace() for ch in seq_id):
                    raise ValueError(
                        "FastqFormat: 'seq_id' may not contain "
                        f"whitespace, got {seq_id!r}"
                    )
                description = record.get("description", "")
                if description is None:
                    description = ""
                if not isinstance(description, str):
                    raise TypeError(
                        "FastqFormat: 'description' must be str"
                    )
                sequence = record.get("sequence", "")
                if not isinstance(sequence, str):
                    raise TypeError(
                        "FastqFormat: 'sequence' must be str"
                    )
                quality = record.get("quality", "")
                if not isinstance(quality, str):
                    raise TypeError(
                        "FastqFormat: 'quality' must be str"
                    )
                if len(quality) != len(sequence):
                    raise ValueError(
                        "FastqFormat: 'quality' length "
                        f"({len(quality)}) must match 'sequence' length "
                        f"({len(sequence)})"
                    )
                if description:
                    header = f"@{seq_id} {description}\n"
                else:
                    header = f"@{seq_id}\n"
                payload = (
                    header
                    + sequence
                    + "\n+\n"
                    + quality
                    + "\n"
                )
                yield payload.encode(encoding)

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
    def _build_record(lines: list[str]) -> Mapping[str, Any]:
        header_line, sequence_line, separator_line, quality_line = lines
        if not header_line.startswith("@"):
            raise ValueError(
                "FastqFormat: expected header line to start with '@', got "
                f"{header_line!r}"
            )
        if not separator_line.startswith("+"):
            raise ValueError(
                "FastqFormat: expected separator line to start with '+', "
                f"got {separator_line!r}"
            )
        if len(quality_line) != len(sequence_line):
            raise ValueError(
                "FastqFormat: quality length "
                f"({len(quality_line)}) does not match sequence length "
                f"({len(sequence_line)})"
            )
        header = header_line[1:].lstrip()
        if not header:
            raise ValueError("FastqFormat: header line missing seq_id")
        split = header.split(None, 1)
        seq_id = split[0]
        description = split[1] if len(split) == 2 else ""
        return {
            "seq_id": seq_id,
            "description": description,
            "sequence": sequence_line,
            "quality": quality_line,
        }
