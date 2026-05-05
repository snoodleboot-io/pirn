"""Shared serialization base for object-store-backed DataStores.

All cloud and local-disk DataStore implementations inherit from this class.
It handles cloudpickle serialization and HMAC signing; subclasses implement
the four raw-bytes IO primitives.

.. note::
    ``cloudpickle.loads`` on attacker-controlled bytes is a remote-code-
    execution sink. Pirn refuses to construct an unsigned store unless
    the caller explicitly passes ``allow_unsigned=True`` to acknowledge
    that the cache backing is in the same trust boundary as the pirn
    process. Production deployments MUST pass a real ``signer``.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from pirn.backends.base.data_store import DataStore

if TYPE_CHECKING:
    from pirn.backends._signer import _Signer

_logger = logging.getLogger(__name__)


class _CloudObjectStore(DataStore):
    """Serialization + signing mixin for object-store backends.

    Subclasses must implement:
        _object_key(content_hash) -> str
        _put_bytes(key, payload)  async
        _get_bytes(key)           async -> bytes   (raise KeyError if missing)
        _has_key(key)             async -> bool
        _delete_key(key)          async
    """

    def __init__(
        self,
        *,
        signer: _Signer | None = None,
        allow_unsigned: bool = False,
    ) -> None:
        if signer is None and not allow_unsigned:
            raise ValueError(
                f"{type(self).__name__}: refusing to construct an unsigned "
                "store. cloudpickle.loads on attacker-controlled bytes is a "
                "remote-code-execution sink. Pass a `signer=` (production) "
                "or `allow_unsigned=True` (single-tenant dev / test only) "
                "to acknowledge the trust-boundary assumption."
            )
        if signer is None and allow_unsigned:
            if os.environ.get("PIRN_ALLOW_UNSIGNED") != "1":
                raise ValueError(
                    f"{type(self).__name__}: allow_unsigned=True requires the "
                    "environment variable PIRN_ALLOW_UNSIGNED=1 to be set. "
                    "This prevents accidental unsigned stores in production. "
                    "Set PIRN_ALLOW_UNSIGNED=1 only in development or test environments."
                )
            _logger.warning(
                "%s constructed without HMAC signing (allow_unsigned=True). "
                "cloudpickle.loads on attacker-controlled bytes is an RCE sink. "
                "Ensure the backing store is within the same trust boundary as this process.",
                type(self).__name__,
            )
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
