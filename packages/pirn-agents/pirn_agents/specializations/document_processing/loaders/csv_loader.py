"""``CsvLoader`` — parse CSV bytes into records using only stdlib (F25-S1).

Needs no optional backend: it decodes UTF-8 and parses rows with the stdlib
:mod:`csv` module. Emits both a flat text rendering (for chunk/embed prose
pipelines) and the structured rows under :attr:`LoadedDocument.records` (for
callers that want per-row ingestion).
"""

from __future__ import annotations

import csv
import io

from pirn_agents.specializations.document_processing.loaders.loaded_document import (
    LoadedDocument,
)
from pirn_agents.specializations.document_processing.loaders.loader import Loader


class CsvLoader(Loader):
    """Parse CSV bytes into structured records plus a text rendering."""

    def __init__(self, *, delimiter: str = ",", row_separator: str = "\n") -> None:
        """Configure the loader.

        Args:
            delimiter: Field delimiter passed to :class:`csv.DictReader`.
            row_separator: String joining rendered rows in the text output.
        """
        self._delimiter = delimiter
        self._row_separator = row_separator

    async def load(self, data: bytes, *, source_id: str | None = None) -> LoadedDocument:
        """Parse the CSV and return records plus a text rendering.

        Args:
            data: The raw CSV bytes (UTF-8, with a header row).
            source_id: Optional identifier recorded on the document.

        Returns:
            A :class:`LoadedDocument` whose ``records`` holds one mapping per row
            and whose ``text`` renders ``key=value`` pairs row by row.

        Raises:
            TypeError: If ``data`` is not bytes.
            ValueError: If the bytes are not valid UTF-8 or cannot be parsed.
        """
        raw = self._require_bytes("CsvLoader", data)
        try:
            decoded = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"CsvLoader: bytes are not valid UTF-8: {exc}") from exc
        try:
            reader = csv.DictReader(io.StringIO(decoded), delimiter=self._delimiter)
            rows = [dict(row) for row in reader]
        except csv.Error as exc:
            raise ValueError(f"CsvLoader: could not parse CSV: {exc}") from exc
        text = self._row_separator.join(
            ", ".join(f"{key}={value}" for key, value in row.items()) for row in rows
        )
        return LoadedDocument(
            text=text,
            metadata={"content_type": "text/csv", "row_count": len(rows)},
            source_id=source_id,
            records=tuple(rows),
        )
