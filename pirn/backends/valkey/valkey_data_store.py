from __future__ import annotations

import logging
import os
from typing import Any

from pirn.backends._signer import _Signer
from pirn.backends.base.data_store import DataStore
from pirn.backends.valkey._lazy_client import _LazyClient

_logger = logging.getLogger(__name__)


class ValKeyDataStore(DataStore):
    """DataStore backed by ValKey.

    Values are cloudpickled and stored under their content hash.  Optional
    HMAC signing guards against tampered values at rest.
    """

    _prefix = "pirn:data:"

    def __init__(
        self,
        *,
        client: Any = None,
        config: Any = None,
        ttl_seconds: int | None = None,
        signer: _Signer | None = None,
        allow_unsigned: bool = False,
    ) -> None:
        """Initialise the data store.

        Args:
            client: An existing ``GlideClient`` instance to reuse.
            config: A ``GlideClientConfiguration`` used to create a client
                lazily on first use.  Mutually exclusive with ``client``.
            ttl_seconds: Optional TTL applied to every key on write.  If
                ``None``, keys do not expire automatically.
            signer: An ``_Signer`` instance for HMAC payload signing.
                Required unless ``allow_unsigned=True`` is set.
            allow_unsigned: If ``True``, the store operates without signing.
                Requires ``PIRN_ALLOW_UNSIGNED=1`` in the environment.

        Raises:
            ValueError: If neither ``signer`` nor ``allow_unsigned=True`` is
                provided, or if ``allow_unsigned=True`` is set without the
                required environment variable.
            TypeError: If neither ``client`` nor ``config`` is provided.
        """
        if signer is None and not allow_unsigned:
            raise ValueError(
                "ValKeyDataStore: refusing to construct an unsigned store. "
                "cloudpickle.loads on attacker-controlled bytes is a "
                "remote-code-execution sink. Pass a `signer=` (production) "
                "or `allow_unsigned=True` (single-tenant dev / test only) "
                "to acknowledge the trust-boundary assumption."
            )
        if signer is None and allow_unsigned:
            if os.environ.get("PIRN_ALLOW_UNSIGNED") != "1":
                raise ValueError(
                    "ValKeyDataStore: allow_unsigned=True requires the environment "
                    "variable PIRN_ALLOW_UNSIGNED=1 to be set. "
                    "This prevents accidental unsigned stores in production. "
                    "Set PIRN_ALLOW_UNSIGNED=1 only in development or test environments."
                )
            _logger.warning(
                "ValKeyDataStore constructed without HMAC signing (allow_unsigned=True). "
                "cloudpickle.loads on attacker-controlled bytes is an RCE sink. "
                "Ensure the backing store is within the same trust boundary as this process.",
            )
        self._client = _LazyClient(client=client, config=config)
        self._ttl = ttl_seconds
        self.__signer = signer

    def _key(self, content_hash: str) -> str:
        """Build the full ValKey key for a content hash.

        Args:
            content_hash: SHA-256 hex digest.

        Returns:
            Key string with the ``pirn:data:`` prefix.
        """
        return f"{self._prefix}{content_hash}"

    async def put(self, content_hash: str, value: Any) -> None:
        """Serialize and store a value under its content hash.

        If a TTL was configured at construction the key is written with
        that expiry.

        Args:
            content_hash: Content-addressable key for the value.
            value: Arbitrary Python object to persist.
        """
        import cloudpickle

        client = await self._client.get()
        payload = cloudpickle.dumps(value)
        if self.__signer is not None:
            payload = self.__signer.sign(payload)
        if self._ttl is not None:
            from glide import ExpirySet, ExpiryType

            expiry = ExpirySet(ExpiryType.SEC, self._ttl)
            await client.set(self._key(content_hash), payload, expiry=expiry)
        else:
            await client.set(self._key(content_hash), payload)

    async def get(self, content_hash: str) -> Any:
        """Retrieve and deserialize the value stored under ``content_hash``.

        Args:
            content_hash: Hash previously passed to :meth:`put`.

        Returns:
            The deserialized Python object.

        Raises:
            KeyError: If no value is stored under ``content_hash``.
            ValueError: If signature verification fails.
        """
        import cloudpickle

        client = await self._client.get()
        payload = await client.get(self._key(content_hash))
        if payload is None:
            raise KeyError(content_hash)
        if self.__signer is not None:
            payload = self.__signer.verify(payload)
        return cloudpickle.loads(payload)

    async def has(self, content_hash: str) -> bool:
        """Return ``True`` if a value is stored under ``content_hash``.

        Args:
            content_hash: Hash to check.

        Returns:
            ``True`` if present, ``False`` otherwise.
        """
        client = await self._client.get()
        return bool(await client.exists([self._key(content_hash)]))

    async def scrub(self, content_hash: str) -> None:
        """Delete the value stored under ``content_hash``.

        Lineage records that reference the hash remain intact.

        Args:
            content_hash: Hash of the value to remove.
        """
        client = await self._client.get()
        await client.delete([self._key(content_hash)])

    async def close(self) -> None:
        """Close the underlying ValKey client if it was created internally."""
        await self._client.close()
