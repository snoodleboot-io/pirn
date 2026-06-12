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
        """Initialise the mixin with signing configuration.

        Args:
            signer: An ``_Signer`` instance used to HMAC-sign payloads before
                writing and verify them after reading.  Required in production.
            allow_unsigned: If ``True``, the store operates without signing.
                Requires the ``PIRN_ALLOW_UNSIGNED=1`` environment variable to
                be set; raises ``ValueError`` otherwise.  Only for
                single-tenant development or test environments.

        Raises:
            ValueError: If neither ``signer`` nor ``allow_unsigned=True`` is
                provided, or if ``allow_unsigned=True`` is set without the
                ``PIRN_ALLOW_UNSIGNED=1`` environment variable.
        """
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
        """Serialize ``value`` with cloudpickle and optionally sign the result.

        Args:
            value: Arbitrary Python object to serialize.

        Returns:
            Raw bytes ready for storage.  If a signer is configured the bytes
            are prefixed with the HMAC signature.
        """
        import cloudpickle

        payload = cloudpickle.dumps(value)
        if self.__signer is not None:
            payload = self.__signer.sign(payload)
        return payload

    def _deserialize(self, payload: bytes) -> Any:
        """Verify the signature (if any) and deserialize bytes back to a Python object.

        Args:
            payload: Raw bytes retrieved from storage.

        Returns:
            The original Python object.

        Raises:
            ValueError: If a signer is configured and the HMAC signature does
                not match (possible tampering).
        """
        import cloudpickle

        if self.__signer is not None:
            payload = self.__signer.verify(payload)
        return cloudpickle.loads(payload)

    def _object_key(self, content_hash: str) -> str:
        """Derive the backend-specific storage key from a content hash.

        Subclasses must override this to map ``content_hash`` to whatever
        key space the backing store uses (a file path, an S3 object key, etc.).

        Args:
            content_hash: SHA-256 hex digest, possibly prefixed with
                ``sha256:``.

        Returns:
            The storage key string for the backing store.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement _object_key()")

    async def _put_bytes(self, key: str, payload: bytes) -> None:
        """Write raw bytes to the backing store under ``key``.

        Args:
            key: Storage key returned by :meth:`_object_key`.
            payload: Serialized (and optionally signed) bytes to store.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement _put_bytes()")

    async def _get_bytes(self, key: str) -> bytes:
        """Read raw bytes from the backing store.

        Args:
            key: Storage key returned by :meth:`_object_key`.

        Returns:
            The bytes previously written by :meth:`_put_bytes`.

        Raises:
            KeyError: If no object exists at ``key``.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement _get_bytes()")

    async def _has_key(self, key: str) -> bool:
        """Return ``True`` if an object exists at ``key`` in the backing store.

        Args:
            key: Storage key returned by :meth:`_object_key`.

        Returns:
            ``True`` if the object exists, ``False`` otherwise.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement _has_key()")

    async def _delete_key(self, key: str) -> None:
        """Delete the object at ``key`` from the backing store.

        Implementations must be idempotent: deleting a non-existent key
        must not raise.

        Args:
            key: Storage key returned by :meth:`_object_key`.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement _delete_key()")

    async def put(self, content_hash: str, value: Any) -> None:
        """Serialize ``value`` and write it to the backing store.

        Args:
            content_hash: Content-addressable key for the value.
            value: Arbitrary Python object to persist.
        """
        payload = self._serialize(value)
        await self._put_bytes(self._object_key(content_hash), payload)

    async def get(self, content_hash: str) -> Any:
        """Read and deserialize the value stored under ``content_hash``.

        Args:
            content_hash: Hash previously passed to :meth:`put`.

        Returns:
            The deserialized Python object.

        Raises:
            KeyError: If no value is stored under ``content_hash``.
            ValueError: If signature verification fails.
        """
        payload = await self._get_bytes(self._object_key(content_hash))
        return self._deserialize(payload)

    async def has(self, content_hash: str) -> bool:
        """Return ``True`` if a value is stored under ``content_hash``.

        Args:
            content_hash: Hash to check.

        Returns:
            ``True`` if present, ``False`` otherwise.
        """
        return await self._has_key(self._object_key(content_hash))

    async def scrub(self, content_hash: str) -> None:
        """Remove the value stored under ``content_hash``.

        Lineage records that reference the hash remain intact.

        Args:
            content_hash: Hash of the value to remove.
        """
        await self._delete_key(self._object_key(content_hash))
