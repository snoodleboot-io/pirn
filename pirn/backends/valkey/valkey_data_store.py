from __future__ import annotations

import pickle
from typing import Any

from pirn.backends.base.data_store import DataStore
from pirn.backends.valkey._lazy_client import _LazyClient


class ValKeyDataStore(DataStore):
    """DataStore backed by ValKey.

    Values are pickled and stored under their content hash.  Optional
    HMAC signing guards against tampered values at rest.
    """

    _prefix = "pirn:data:"
    _pickle_protocol = 5

    def __init__(
        self,
        *,
        client: Any = None,
        config: Any = None,
        ttl_seconds: int | None = None,
        signing_key: bytes | None = None,
    ) -> None:
        self._client = _LazyClient(client=client, config=config)
        self._ttl = ttl_seconds
        self._signing_key = signing_key

    def _key(self, content_hash: str) -> str:
        return f"{self._prefix}{content_hash}"

    async def put(self, content_hash: str, value: Any) -> None:
        from pirn.backends._signing import sign as _sign

        client = await self._client.get()
        payload = pickle.dumps(value, protocol=self._pickle_protocol)
        if self._signing_key is not None:
            payload = _sign(payload, self._signing_key)
        if self._ttl is not None:
            from glide import ExpirySet, ExpiryType
            expiry = ExpirySet(ExpiryType.SEC, self._ttl)
            await client.set(self._key(content_hash), payload, expiry=expiry)
        else:
            await client.set(self._key(content_hash), payload)

    async def get(self, content_hash: str) -> Any:
        from pirn.backends._signing import verify as _verify

        client = await self._client.get()
        payload = await client.get(self._key(content_hash))
        if payload is None:
            raise KeyError(content_hash)
        if self._signing_key is not None:
            payload = _verify(payload, self._signing_key)
        return pickle.loads(payload)  # noqa: S301

    async def has(self, content_hash: str) -> bool:
        client = await self._client.get()
        return bool(await client.exists([self._key(content_hash)]))

    async def scrub(self, content_hash: str) -> None:
        client = await self._client.get()
        await client.delete([self._key(content_hash)])

    async def close(self) -> None:
        await self._client.close()
