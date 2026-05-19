"""``ObjectStoreTransport`` — transport backed by any :class:`~pirn.domains.connectors.object_store.ObjectStore`.

Wraps S3Store, GCSStore, AzureBlobStore, LocalFilesystemStore (or any future
``ObjectStore`` subclass) and stores knot outputs as serialised blobs:

    {prefix}/{run_id}/{knot_id}/{sha256[:16]}.bin

Lifecycle
---------
* ``begin_run``: registers the run; no I/O.
* ``write``:     serialises the value, writes to the store, stashes the key.
* ``read``:      streams all chunks from the store, deserialises, returns value.
* ``exists``:    lists the key prefix; returns True if the exact key appears.
* ``end_run``:   deletes every key written for the run (or skips deletion on
                 failure when ``keep_on_failure=True`` — useful for post-mortem
                 inspection of what each knot produced before the run crashed).

Cloud-provider agnosticism
--------------------------
The caller constructs the ``ObjectStore`` (credentials, bucket, region, …) and
hands it in.  ``ObjectStoreTransport`` never imports aioboto3 / gcloud / azure
directly; it only calls the four methods of the ``ObjectStore`` interface.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from pirn.core.transport.data_transport import DataTransport
from pirn.core.transport.serializers.serializer_registry import SerializerRegistry
from pirn.core.transport.transport_error import TransportError
from pirn.core.transport.transport_handle import TransportHandle
from pirn.domains.connectors.object_store import ObjectStore

_log = logging.getLogger(__name__)


class ObjectStoreTransport(DataTransport):
    """Store knot outputs in any cloud or local :class:`ObjectStore`.

    Parameters
    ----------
    store:
        A concrete ``ObjectStore`` (S3Store, GCSStore, AzureBlobStore,
        LocalFilesystemStore, …).  The caller is responsible for its
        lifecycle (credentials, connection pooling, closing).
    prefix:
        Key namespace prepended to every object key.  Defaults to ``pirn``.
        Must not start or end with ``/``.
    keep_on_failure:
        If True, skip key deletion in ``end_run`` when ``success=False``.
        Objects remain in the store for post-mortem inspection; they will
        accumulate if not cleaned up manually or via bucket lifecycle rules.
    serializer_registry:
        Registry of type→serialiser mappings.  Defaults to
        :meth:`~pirn.core.transport.serializers.serializer_registry.SerializerRegistry.default`.
    """

    def __init__(
        self,
        *,
        store: ObjectStore,
        prefix: str = "pirn",
        keep_on_failure: bool = False,
        serializer_registry: SerializerRegistry | None = None,
    ) -> None:
        if not prefix or prefix.startswith("/") or prefix.endswith("/"):
            raise ValueError(
                "ObjectStoreTransport: prefix must be non-empty and must not start or end with '/'"
            )
        self._store = store
        self._prefix = prefix
        self._keep_on_failure = keep_on_failure
        self._registry = serializer_registry or SerializerRegistry.default()
        self._run_keys: dict[str, list[str]] = {}

    @property
    def transport_id(self) -> str:
        return f"object_store:{type(self._store).__name__}:{self._prefix}"

    async def begin_run(self, run_id: str) -> None:
        self._run_keys[run_id] = []

    async def write(self, run_id: str, knot_id: str, value: Any) -> TransportHandle:
        if run_id not in self._run_keys:
            raise TransportError("ObjectStoreTransport: begin_run() must be called before write()")
        serialiser = self._registry.get(value)
        try:
            raw = serialiser.serialise(value)
        except Exception as exc:
            raise TransportError(
                f"ObjectStoreTransport: failed to serialise output of knot {knot_id!r}: {exc}"
            ) from exc
        content_hash = hashlib.sha256(raw).hexdigest()[:16]
        safe_run = run_id.replace("/", "_").replace(":", "_")
        safe_knot = knot_id.replace("/", "_").replace(":", "_")
        key = f"{self._prefix}/{safe_run}/{safe_knot}/{content_hash}.bin"
        try:
            await self._store.put(key, raw)
        except Exception as exc:
            raise TransportError(
                f"ObjectStoreTransport: failed to write key {key!r}: {exc}"
            ) from exc
        self._run_keys[run_id].append(key)
        type_name = f"{type(value).__module__}.{type(value).__qualname__}"
        return TransportHandle(
            transport_id=self.transport_id,
            key=key,
            type_name=type_name,
            size_bytes=len(raw),
            checksum=content_hash,
        )

    async def read(self, handle: TransportHandle) -> Any:
        try:
            stream = await self._store.get(handle.key)
            chunks: list[bytes] = []
            async for chunk in stream:
                chunks.append(chunk)
            raw = b"".join(chunks)
        except Exception as exc:
            raise TransportError(
                f"ObjectStoreTransport: failed to read key {handle.key!r}: {exc}"
            ) from exc
        serialiser = self._registry.get_by_type_name(handle.type_name)
        try:
            return serialiser.deserialise(raw, handle.type_name)
        except Exception as exc:
            raise TransportError(
                f"ObjectStoreTransport: cannot deserialise {handle.type_name} "
                f"from key {handle.key!r}: {exc}"
            ) from exc

    async def exists(self, handle: TransportHandle) -> bool:
        try:
            listing = await self._store.list(prefix=handle.key)
            async for key in listing:
                if key == handle.key:
                    return True
            return False
        except Exception:
            return False

    async def end_run(self, run_id: str, *, success: bool) -> None:
        keys = self._run_keys.pop(run_id, [])
        if not keys:
            return
        if not success and self._keep_on_failure:
            _log.info(
                "ObjectStoreTransport: retaining %d key(s) for failed run %s "
                "(keep_on_failure=True)",
                len(keys),
                run_id,
            )
            return
        errors: list[str] = []
        for key in keys:
            try:
                await self._store.delete(key)
            except Exception as exc:
                errors.append(f"{key!r}: {exc}")
        if errors:
            _log.warning(
                "ObjectStoreTransport: failed to delete %d key(s) for run %s: %s",
                len(errors),
                run_id,
                "; ".join(errors),
            )
