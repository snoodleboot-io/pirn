"""``FastaFormat`` — FASTA sequence encoder/decoder.

FASTA is a simple text format used in bioinformatics: each record is a
header line (``>seq_id description``) followed by one or more sequence
lines. We parse it directly with stdlib only — no external dep is
required for the basic streaming round-trip path.

The optional ``pyfaidx`` package is used only when callers want indexed
random-access reads against a local file; it is not required for the
:meth:`read` / :meth:`write` API exposed here. It remains a soft
dependency declared via ``pirn[genomics]``.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Mapping

from pirn.domains.connectors.file_formats.streaming_file_format import (
    StreamingFileFormat,
)


class FastaFormat(StreamingFileFormat):
    """FASTA file format implemented with stdlib parsing.

    Args:
        encoding: Text encoding for the byte stream. Defaults to
            ``"utf-8"``.
        line_width: Maximum sequence line width on encode. Defaults to
            ``80`` (a long-standing FASTA convention).
    """

    def __init__(
        self,
        encoding: str = "utf-8",
        line_width: int = 80,
    ) -> None:
        if not isinstance(encoding, str):
            raise TypeError("FastaFormat: encoding must be str")
        if not encoding:
            raise ValueError("FastaFormat: encoding must be non-empty")
        if not isinstance(line_width, int) or isinstance(line_width, bool):
            raise TypeError("FastaFormat: line_width must be int")
        if line_width < 1:
            raise ValueError(
                "FastaFormat: line_width must be a positive integer"
            )
        self._encoding = encoding
        self._line_width = line_width

    @property
    def name(self) -> str:
        return "fasta"

    @property
    def encoding(self) -> str:
        return self._encoding

    @property
    def line_width(self) -> int:
        return self._line_width

    async def read(
        self, body: AsyncIterator[bytes]
    ) -> AsyncIterator[Mapping[str, Any]]:
        encoding = self._encoding

        async def _iter() -> AsyncIterator[Mapping[str, Any]]:
            buffered = bytearray()
            current_seq_id: str | None = None
            current_description: str = ""
            current_sequence_parts: list[str] = []

            async for chunk in body:
                buffered.extend(chunk)
                while True:
                    newline_index = buffered.find(b"\n")
                    if newline_index == -1:
                        break
                    raw_line = bytes(buffered[:newline_index])
                    del buffered[: newline_index + 1]
                    line = raw_line.decode(encoding).rstrip("\r")
                    if not line:
                        continue
                    if line.startswith(">"):
                        if current_seq_id is not None:
                            yield {
                                "seq_id": current_seq_id,
                                "description": current_description,
                                "sequence": "".join(
                                    current_sequence_parts
                                ),
                            }
                        header = line[1:].lstrip()
                        if not header:
                            raise ValueError(
                                "FastaFormat: header line missing seq_id"
                            )
                        split = header.split(None, 1)
                        current_seq_id = split[0]
                        current_description = (
                            split[1] if len(split) == 2 else ""
                        )
                        current_sequence_parts = []
                    else:
                        if current_seq_id is None:
                            raise ValueError(
                                "FastaFormat: sequence data before any "
                                "header"
                            )
                        current_sequence_parts.append(line.strip())

            # Flush trailing partial line (no newline at EOF).
            if buffered:
                line = bytes(buffered).decode(encoding).rstrip("\r")
                buffered.clear()
                if line:
                    if line.startswith(">"):
                        if current_seq_id is not None:
                            yield {
                                "seq_id": current_seq_id,
                                "description": current_description,
                                "sequence": "".join(
                                    current_sequence_parts
                                ),
                            }
                        header = line[1:].lstrip()
                        if not header:
                            raise ValueError(
                                "FastaFormat: header line missing seq_id"
                            )
                        split = header.split(None, 1)
                        current_seq_id = split[0]
                        current_description = (
                            split[1] if len(split) == 2 else ""
                        )
                        current_sequence_parts = []
                    else:
                        if current_seq_id is None:
                            raise ValueError(
                                "FastaFormat: sequence data before any "
                                "header"
                            )
                        current_sequence_parts.append(line.strip())

            if current_seq_id is not None:
                yield {
                    "seq_id": current_seq_id,
                    "description": current_description,
                    "sequence": "".join(current_sequence_parts),
                }

        return _iter()

    async def write(
        self, records: AsyncIterator[Mapping[str, Any]]
    ) -> AsyncIterator[bytes]:
        encoding = self._encoding
        line_width = self._line_width

        async def _iter() -> AsyncIterator[bytes]:
            async for record in records:
                seq_id = record.get("seq_id")
                if not isinstance(seq_id, str) or not seq_id:
                    raise ValueError(
                        "FastaFormat: each record must have a non-empty "
                        "string 'seq_id'"
                    )
                if any(ch.isspace() for ch in seq_id):
                    raise ValueError(
                        "FastaFormat: 'seq_id' may not contain "
                        f"whitespace, got {seq_id!r}"
                    )
                description = record.get("description", "")
                if description is None:
                    description = ""
                if not isinstance(description, str):
                    raise TypeError(
                        "FastaFormat: 'description' must be str"
                    )
                sequence = record.get("sequence", "")
                if sequence is None:
                    sequence = ""
                if not isinstance(sequence, str):
                    raise TypeError(
                        "FastaFormat: 'sequence' must be str"
                    )
                if description:
                    header_line = f">{seq_id} {description}\n"
                else:
                    header_line = f">{seq_id}\n"
                yield header_line.encode(encoding)
                if sequence:
                    for start in range(0, len(sequence), line_width):
                        chunk = sequence[start : start + line_width]
                        yield (chunk + "\n").encode(encoding)
                else:
                    yield b"\n"

        return _iter()
