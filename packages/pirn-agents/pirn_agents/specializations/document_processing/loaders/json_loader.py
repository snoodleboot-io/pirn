"""``JsonLoader`` — parse JSON bytes into records using only stdlib (F25-S1).

Needs no optional backend: it decodes UTF-8 and parses with the stdlib
:mod:`json` module. A top-level array of objects becomes one record per element;
any other JSON value becomes a single record. A pretty-printed rendering is
emitted as :attr:`LoadedDocument.text` for prose-style chunk/embed pipelines.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pirn_agents.specializations.document_processing.loaders.loaded_document import (
    LoadedDocument,
)
from pirn_agents.specializations.document_processing.loaders.loader import Loader


class JsonLoader(Loader):
    """Parse JSON bytes into structured records plus a text rendering."""

    def __init__(self, *, indent: int = 2) -> None:
        """Configure the loader.

        Args:
            indent: Indentation used when rendering the parsed JSON to text.
        """
        self._indent = indent

    async def load(self, data: bytes, *, source_id: str | None = None) -> LoadedDocument:
        """Parse the JSON and return records plus a text rendering.

        Args:
            data: The raw JSON bytes (UTF-8).
            source_id: Optional identifier recorded on the document.

        Returns:
            A :class:`LoadedDocument` whose ``records`` holds one mapping per
            top-level array element (or a single mapping otherwise) and whose
            ``text`` is the pretty-printed JSON.

        Raises:
            TypeError: If ``data`` is not bytes.
            ValueError: If the bytes are not valid UTF-8 or valid JSON.
        """
        raw = self._require_bytes("JsonLoader", data)
        try:
            decoded = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"JsonLoader: bytes are not valid UTF-8: {exc}") from exc
        try:
            parsed: Any = json.loads(decoded)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JsonLoader: could not parse JSON: {exc}") from exc
        records = self._to_records(parsed)
        text = json.dumps(parsed, indent=self._indent, ensure_ascii=False, sort_keys=True)
        return LoadedDocument(
            text=text,
            metadata={"content_type": "application/json", "record_count": len(records)},
            source_id=source_id,
            records=records,
        )

    @staticmethod
    def _to_records(parsed: Any) -> tuple[Mapping[str, Any], ...]:
        """Normalize a parsed JSON value into a tuple of record mappings."""
        if isinstance(parsed, list):
            return tuple(item if isinstance(item, dict) else {"value": item} for item in parsed)
        if isinstance(parsed, dict):
            return (parsed,)
        return ({"value": parsed},)
