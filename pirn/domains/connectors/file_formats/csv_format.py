"""``CsvFormat`` — comma-separated values encoder/decoder using stdlib ``csv``.

Streamable both directions: lines are decoded incrementally from the
byte stream, and rows are encoded one-at-a-time as the records arrive.

No optional dependency — this format always works on a stock pirn
install.
"""

from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from pirn.domains.connectors.file_formats.streaming_file_format import (
    StreamingFileFormat,
)


class CsvFormat(StreamingFileFormat):
    """CSV file format backed by the stdlib ``csv`` module.

    Args:
        delimiter: Single-character field delimiter. Defaults to ``","``.
        quotechar: Single-character quote delimiter. Defaults to ``'"'``.
        has_header: When ``True``, the first row holds column names.
            When ``False``, ``column_names`` is required.
        column_names: Explicit column names. Required when
            ``has_header=False``; optional otherwise.
        encoding: Text encoding used on the byte stream. Defaults to
            ``"utf-8"``.
    """

    def __init__(
        self,
        delimiter: str = ",",
        quotechar: str = '"',
        has_header: bool = True,
        column_names: Sequence[str] | None = None,
        encoding: str = "utf-8",
    ) -> None:
        if not isinstance(delimiter, str):
            raise TypeError(
                f"{type(self).__name__}: delimiter must be str"
            )
        if len(delimiter) != 1:
            raise ValueError(
                f"{type(self).__name__}: delimiter must be a single "
                f"character, got {delimiter!r}"
            )
        if not isinstance(quotechar, str):
            raise TypeError(
                f"{type(self).__name__}: quotechar must be str"
            )
        if len(quotechar) != 1:
            raise ValueError(
                f"{type(self).__name__}: quotechar must be a single "
                f"character, got {quotechar!r}"
            )
        if not isinstance(has_header, bool):
            raise TypeError(
                f"{type(self).__name__}: has_header must be bool"
            )
        if column_names is not None:
            if isinstance(column_names, (str, bytes)):
                raise TypeError(
                    f"{type(self).__name__}: column_names must be a "
                    "sequence of strings"
                )
            column_names = tuple(column_names)
            for name in column_names:
                if not isinstance(name, str):
                    raise TypeError(
                        f"{type(self).__name__}: every entry in "
                        "column_names must be str"
                    )
        if not has_header and column_names is None:
            raise ValueError(
                f"{type(self).__name__}: column_names is required when "
                "has_header=False"
            )
        if not isinstance(encoding, str):
            raise TypeError(
                f"{type(self).__name__}: encoding must be str"
            )
        if not encoding:
            raise ValueError(
                f"{type(self).__name__}: encoding must be non-empty"
            )

        self._delimiter = delimiter
        self._quotechar = quotechar
        self._has_header = has_header
        self._column_names: tuple[str, ...] | None = column_names
        self._encoding = encoding

    @property
    def name(self) -> str:
        return "csv"

    @property
    def delimiter(self) -> str:
        return self._delimiter

    @property
    def quotechar(self) -> str:
        return self._quotechar

    @property
    def has_header(self) -> bool:
        return self._has_header

    @property
    def column_names(self) -> tuple[str, ...] | None:
        return self._column_names

    @property
    def encoding(self) -> str:
        return self._encoding

    async def read(
        self, body: AsyncIterator[bytes]
    ) -> AsyncIterator[Mapping[str, Any]]:
        payload = await self._drain_bytes(body)
        text = payload.decode(self._encoding)
        delimiter = self._delimiter
        quotechar = self._quotechar
        has_header = self._has_header
        configured_columns = self._column_names

        async def _iter() -> AsyncIterator[Mapping[str, Any]]:
            text_buffer = io.StringIO(text)
            if has_header:
                reader = csv.DictReader(
                    text_buffer,
                    delimiter=delimiter,
                    quotechar=quotechar,
                )
                for row in reader:
                    yield {key: value for key, value in row.items()}
                return

            if configured_columns is None:
                raise RuntimeError(
                    "CsvFormat: column_names missing in headerless mode"
                )
            row_reader = csv.reader(
                text_buffer,
                delimiter=delimiter,
                quotechar=quotechar,
            )
            for raw_row in row_reader:
                yield dict(zip(configured_columns, raw_row, strict=False))

        return _iter()

    async def write(
        self, records: AsyncIterator[Mapping[str, Any]]
    ) -> AsyncIterator[bytes]:
        materialised = await self._drain_records(records)
        if self._column_names is not None:
            fieldnames: list[str] = list(self._column_names)
        elif materialised:
            fieldnames = list(materialised[0].keys())
        else:
            fieldnames = []

        text_buffer = io.StringIO()
        writer = csv.DictWriter(
            text_buffer,
            fieldnames=fieldnames,
            delimiter=self._delimiter,
            quotechar=self._quotechar,
            lineterminator="\n",
        )
        if self._has_header and fieldnames:
            writer.writeheader()
        for record in materialised:
            writer.writerow(
                {field: record.get(field) for field in fieldnames}
            )

        payload = text_buffer.getvalue().encode(self._encoding)

        async def _iter() -> AsyncIterator[bytes]:
            yield payload

        return _iter()
