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
        return f"{self._prefix}{content_hash}"

    async def put(self, content_hash: str, value: Any) -> None:
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
        import cloudpickle

        client = await self._client.get()
        payload = await client.get(self._key(content_hash))
        if payload is None:
            raise KeyError(content_hash)
        if self.__signer is not None:
            payload = self.__signer.verify(payload)
        return cloudpickle.loads(payload)

    async def has(self, content_hash: str) -> bool:
        client = await self._client.get()
        return bool(await client.exists([self._key(content_hash)]))

    async def scrub(self, content_hash: str) -> None:
        client = await self._client.get()
        await client.delete([self._key(content_hash)])

    async def close(self) -> None:
        await self._client.close()
