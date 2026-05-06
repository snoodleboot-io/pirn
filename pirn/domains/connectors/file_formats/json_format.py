"""``JsonFormat`` — whole-document JSON encoder/decoder using stdlib ``json``.

Two shapes:

* ``array_root=True`` (default): the file is a JSON array of objects.
  ``read`` yields each element; ``write`` emits the array.
* ``array_root=False``: the file is a single JSON object treated as one
  record. ``read`` yields the single object; ``write`` requires exactly
  one record.

Strictly speaking this is not incrementally streamable — the whole
payload must be parsed before yielding records. Inherits from
:class:`StreamingFileFormat` for API consistency; downstream consumers
should look at ``streaming`` only as advisory.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn.domains.connectors.file_formats.streaming_file_format import (
    StreamingFileFormat,
)


class JsonFormat(StreamingFileFormat):
    """JSON file format backed by stdlib ``json``.

    Args:
        array_root: When ``True`` the file is a JSON array of records.
            When ``False`` the file is a single JSON object treated as
            one record (write requires exactly one record).
        encoding: Text encoding for the byte stream. Defaults to
            ``"utf-8"``.
    """

    def __init__(
        self,
        array_root: bool = True,
        encoding: str = "utf-8",
    ) -> None:
        if not isinstance(array_root, bool):
            raise TypeError("JsonFormat: array_root must be bool")
        if not isinstance(encoding, str):
            raise TypeError("JsonFormat: encoding must be str")
        if not encoding:
            raise ValueError("JsonFormat: encoding must be non-empty")
        self._array_root = array_root
        self._encoding = encoding

    @property
    def name(self) -> str:
        return "json"

    @property
    def array_root(self) -> bool:
        return self._array_root

    @property
    def encoding(self) -> str:
        return self._encoding

    async def read(self, body: AsyncIterator[bytes]) -> AsyncIterator[Mapping[str, Any]]:
        payload = await self._drain_bytes(body)
        if not payload.strip():
            parsed: Any = [] if self._array_root else {}
        else:
            parsed = json.loads(payload.decode(self._encoding))

        if self._array_root:
            if not isinstance(parsed, list):
                raise ValueError(
                    f"JsonFormat: expected JSON array at root, got {type(parsed).__name__}"
                )
            records: list[Mapping[str, Any]] = []
            for item in parsed:
                if not isinstance(item, dict):
                    raise ValueError(
                        f"JsonFormat: array element is not a JSON object: {type(item).__name__}"
                    )
                records.append(item)
        else:
            if not isinstance(parsed, dict):
                raise ValueError(
                    f"JsonFormat: expected JSON object at root, got {type(parsed).__name__}"
                )
            records = [parsed] if parsed else []

        async def _iter() -> AsyncIterator[Mapping[str, Any]]:
            for record in records:
                yield record

        return _iter()

    async def write(self, records: AsyncIterator[Mapping[str, Any]]) -> AsyncIterator[bytes]:
        materialised = await self._drain_records(records)
        rows = [dict(record) for record in materialised]

        if self._array_root:
            payload = json.dumps(rows).encode(self._encoding)
        else:
            if len(rows) > 1:
                raise ValueError(
                    f"JsonFormat: array_root=False requires at most one record, got {len(rows)}"
                )
            single = rows[0] if rows else {}
            payload = json.dumps(single).encode(self._encoding)

        async def _iter() -> AsyncIterator[bytes]:
            yield payload

        return _iter()
