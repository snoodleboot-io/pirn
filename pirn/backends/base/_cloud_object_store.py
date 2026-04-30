"""Shared serialization base for object-store-backed DataStores.

All cloud and local-disk DataStore implementations inherit from this class.
It handles cloudpickle serialization and optional HMAC signing; subclasses
implement the four raw-bytes IO primitives.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pirn.backends.base.data_store import DataStore

if TYPE_CHECKING:
    from pirn.backends._signer import _Signer


class _CloudObjectStore(DataStore):
    """Serialization + signing mixin for object-store backends.

    Subclasses must implement:
        _object_key(content_hash) -> str
        _put_bytes(key, payload)  async
        _get_bytes(key)           async -> bytes   (raise KeyError if missing)
        _has_key(key)             async -> bool
        _delete_key(key)          async
    """

    def __init__(self, *, signer: _Signer | None = None) -> None:
        self.__signer = signer

    def _serialize(self, value: Any) -> bytes:
        import cloudpickle

        payload = cloudpickle.dumps(value)
        if self.__signer is not None:
            payload = self.__signer.sign(payload)
        return payload

    def _deserialize(self, payload: bytes) -> Any:
        import cloudpickle

        if self.__signer is not None:
            payload = self.__signer.verify(payload)
        return cloudpickle.loads(payload)

    def _object_key(self, content_hash: str) -> str:
        raise NotImplementedError(f"{type(self).__name__} must implement _object_key()")

    async def _put_bytes(self, key: str, payload: bytes) -> None:
        raise NotImplementedError(f"{type(self).__name__} must implement _put_bytes()")

    async def _get_bytes(self, key: str) -> bytes:
        raise NotImplementedError(f"{type(self).__name__} must implement _get_bytes()")

    async def _has_key(self, key: str) -> bool:
        raise NotImplementedError(f"{type(self).__name__} must implement _has_key()")

    async def _delete_key(self, key: str) -> None:
        raise NotImplementedError(f"{type(self).__name__} must implement _delete_key()")

    async def put(self, content_hash: str, value: Any) -> None:
        payload = self._serialize(value)
        await self._put_bytes(self._object_key(content_hash), payload)

    async def get(self, content_hash: str) -> Any:
        payload = await self._get_bytes(self._object_key(content_hash))
        return self._deserialize(payload)

    async def has(self, content_hash: str) -> bool:
        return await self._has_key(self._object_key(content_hash))

    async def scrub(self, content_hash: str) -> None:
        await self._delete_key(self._object_key(content_hash))
