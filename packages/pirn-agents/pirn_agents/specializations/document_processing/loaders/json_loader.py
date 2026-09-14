"""``JsonLoader`` — parse JSON bytes into records using only stdlib (F25-S1).

Needs no optional backend: it decodes UTF-8 and parses with the stdlib
:mod:`json` module. A top-level array of objects becomes one record per element;
any other JSON value becomes a single record. A pretty-printed rendering is
emitted as :attr:`LoadedDocument.text` for prose-style chunk/embed pipelines.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, TypeGuard

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
    def _to_records(parsed: object) -> tuple[Mapping[str, Any], ...]:
        """Normalize a parsed JSON value into a tuple of record mappings."""
        if JsonLoader._is_array(parsed):
            return tuple(JsonLoader._to_record(item) for item in parsed)
        return (JsonLoader._to_record(parsed),)

    @staticmethod
    def _to_record(value: object) -> Mapping[str, Any]:
        """Keep a JSON object as the record; wrap any other value as ``{"value": ...}``."""
        if JsonLoader._is_object(value):
            return value
        return {"value": value}

    @staticmethod
    def _is_array(value: object) -> TypeGuard[list[object]]:
        """Narrow a decoded JSON value to a JSON array."""
        return isinstance(value, list)

    @staticmethod
    def _is_object(value: object) -> TypeGuard[dict[str, Any]]:
        """Narrow a decoded JSON value to a JSON object (string keys by the JSON grammar)."""
        return isinstance(value, dict)
