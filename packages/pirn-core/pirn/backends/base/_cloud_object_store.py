"""Shared serialization base for object-store-backed DataStores.

All cloud and local-disk DataStore implementations inherit from this class.
It handles cloudpickle serialization and HMAC signing, and — for the cloud
backends — composes over a connector :class:`~pirn.connectors.object_store.ObjectStore`
that owns the SDK client: the client is opened once on first use and released
by :meth:`close` (PIR-869). A subclass either supplies that store through
:meth:`_build_object_store` (S3/GCS/Azure) or, when it has no connector
counterpart, overrides the four raw-bytes IO primitives directly (local disk,
whose atomic-rename write has no ``ObjectStore`` equivalent).

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
    from pirn.backends.signer import Signer
    from pirn.connectors.object_store import ObjectStore

_logger = logging.getLogger(__name__)


class _CloudObjectStore(DataStore):
    """Serialization + signing base for object-store backends.

    Subclasses either implement ``_build_object_store() -> ObjectStore`` (the
    default primitives then delegate ``put``/``get``/``has``/``scrub`` to that
    store, translating its not-found error into ``KeyError``), or override the
    primitives themselves:

        _put_bytes(key, payload)  async
        _get_bytes(key)           async -> bytes   (raise KeyError if missing)
        _has_key(key)             async -> bool
        _delete_key(key)          async

    ``_object_key(content_hash)`` maps a content hash onto the backing store's
    key space; the default is ``{prefix}{hash-without-sha256:}``.
    """

    def __init__(
        self,
        *,
        signer: Signer | None = None,
        allow_unsigned: bool = False,
        prefix: str = "",
    ) -> None:
        """Initialise the base with signing configuration.

        Args:
            signer: An ``Signer`` instance used to HMAC-sign payloads before
                writing and verify them after reading.  Required in production.
            allow_unsigned: If ``True``, the store operates without signing.
                Requires the ``PIRN_ALLOW_UNSIGNED=1`` environment variable to
                be set; raises ``ValueError`` otherwise.  Only for
                single-tenant development or test environments.
            prefix: Key prefix every object key produced by the default
                :meth:`_object_key` starts with (``"pirn/data/"`` for the cloud
                stores).

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
        self._prefix = prefix
        self.__object_store: ObjectStore | None = None

    # ------------------------------------------------------------ signing

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

    # ------------------------------------------------------- composition

    def _build_object_store(self) -> ObjectStore:
        """Construct the connector ``ObjectStore`` this data store delegates to.

        Called once, lazily, on the first operation; the result is held until
        :meth:`close`. A subclass that overrides the four IO primitives
        instead never triggers it.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement _build_object_store()")

    def _object_store(self) -> ObjectStore:
        """The held ``ObjectStore``, building it on first use."""
        if self.__object_store is None:
            self.__object_store = self._build_object_store()
        return self.__object_store

    async def close(self) -> None:
        """Release the held ``ObjectStore`` (and its SDK client), if any.

        Safe to call repeatedly; the next operation lazily rebuilds the store,
        so a data store shared between tapestries survives the first one
        closing (see :meth:`DataStore.close`).
        """
        store, self.__object_store = self.__object_store, None
        if store is not None:
            await store.close()

    # --------------------------------------------------------- primitives

    def _object_key(self, content_hash: str) -> str:
        """Derive the backend-specific storage key from a content hash.

        The default strips an optional ``sha256:`` prefix and prepends the
        configured ``prefix``; a backend with a different key space (a file
        path, say) overrides it.

        Args:
            content_hash: SHA-256 hex digest, possibly prefixed with
                ``sha256:``.

        Returns:
            The storage key string for the backing store.
        """
        clean = content_hash.removeprefix("sha256:")
        return f"{self._prefix}{clean}"

    async def _put_bytes(self, key: str, payload: bytes) -> None:
        """Write raw bytes to the backing store under ``key``.

        Args:
            key: Storage key returned by :meth:`_object_key`.
            payload: Serialized (and optionally signed) bytes to store.
        """
        await self._object_store().put(key, payload)

    async def _get_bytes(self, key: str) -> bytes:
        """Read raw bytes from the backing store.

        Args:
            key: Storage key returned by :meth:`_object_key`.

        Returns:
            The bytes previously written by :meth:`_put_bytes`.

        Raises:
            KeyError: If no object exists at ``key``.
        """
        store = self._object_store()
        chunks: list[bytes] = []
        try:
            async for chunk in await store.get(key):
                chunks.append(chunk)
        except Exception as exc:
            if store.is_not_found(exc):
                raise KeyError(key) from exc
            raise
        return b"".join(chunks)

    async def _has_key(self, key: str) -> bool:
        """Return ``True`` if an object exists at ``key`` in the backing store.

        Args:
            key: Storage key returned by :meth:`_object_key`.

        Returns:
            ``True`` if the object exists, ``False`` otherwise.
        """
        return await self._object_store().exists(key)

    async def _delete_key(self, key: str) -> None:
        """Delete the object at ``key`` from the backing store.

        Implementations must be idempotent: deleting a non-existent key
        must not raise.

        Args:
            key: Storage key returned by :meth:`_object_key`.
        """
        await self._object_store().delete(key)

    # ------------------------------------------------------ DataStore API

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
