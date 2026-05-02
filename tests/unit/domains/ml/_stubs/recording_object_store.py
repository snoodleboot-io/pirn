"""Recording in-memory stub :class:`ObjectStore` for tests."""

from __future__ import annotations

from typing import AsyncIterator

from pirn.domains.connectors.object_store import ObjectStore


class RecordingObjectStore(ObjectStore):
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.put_calls: list[str] = []
        self.deleted: list[str] = []

    async def get(self, key: str) -> AsyncIterator[bytes]:
        self._validate_key(key)

        async def _iterator() -> AsyncIterator[bytes]:
            yield self.objects[key]

        return _iterator()

    async def put(
        self, key: str, body: AsyncIterator[bytes] | bytes
    ) -> None:
        self._validate_key(key)
        if isinstance(body, (bytes, bytearray)):
            self.objects[key] = bytes(body)
        else:
            chunks: list[bytes] = []
            async for chunk in body:
                chunks.append(chunk)
            self.objects[key] = b"".join(chunks)
        self.put_calls.append(key)

    async def delete(self, key: str) -> None:
        self._validate_key(key)
        self.objects.pop(key, None)
        self.deleted.append(key)

    async def list(self, prefix: str = "") -> AsyncIterator[str]:
        async def _iterator() -> AsyncIterator[str]:
            for key in sorted(self.objects):
                if key.startswith(prefix):
                    yield key

        return _iterator()
