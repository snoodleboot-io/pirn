"""``ValkeyTransport`` — transport backed by Valkey or Redis via ``valkey-glide``.

Supports two key-naming strategies:

content_addressed (default)
    Key = ``pirn:{run_id}:{knot_id}:{hash}``. Each write produces a
    unique, immutable key. Safe for concurrent runs. Cleaned up by
    :meth:`end_run` (deletes all keys for the run) or by TTL if
    cleanup fails.

write_over
    Key = ``pirn:latest:{slot_name}``. Each write replaces whatever was
    previously stored at that key. Intended for "current state"
    semantics: dashboards, model serving, real-time alerting. No per-run
    scoping; the most recent write always wins.

Why ``valkey-glide``
--------------------
``valkey-glide`` (the AWS-originated, now Valkey-maintained async client)
supports both the Redis and Valkey protocols transparently, so a single
transport class works with Redis OSS, Valkey, AWS ElastiCache, and
Google Cloud Memorystore. It provides native asyncio support, cluster
mode, TLS, and connection pooling.

Install: ``pip install pirn[valkey]``
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from pirn.core.transport.data_transport import DataTransport
from pirn.core.transport.serializers.serializer_registry import SerializerRegistry
from pirn.core.transport.transport_error import TransportError
from pirn.core.transport.transport_handle import TransportHandle

_log = logging.getLogger(__name__)


class ValkeyTransport(DataTransport):
    """Store knot outputs in Valkey or Redis using ``valkey-glide``.

    Parameters
    ----------
    host:
        Hostname of the Valkey/Redis server.
    port:
        Port number. Defaults to 6379.
    ttl_sec:
        Time-to-live in seconds applied to every written key. Acts as a
        safety net: keys are deleted by :meth:`end_run` on normal
        completion, but TTL ensures cleanup even after a process crash.
        Defaults to 3600 (1 hour). Set to 0 to disable TTL.
    mode:
        ``"content_addressed"`` (default) or ``"write_over"``. In
        ``write_over`` mode, *slot_name* is required.
    slot_name:
        Named slot used when *mode* is ``"write_over"``. The same key
        is overwritten on every run.
    cluster_mode:
        If True, use ``GlideClusterClient`` instead of ``GlideClient``.
    tls:
        If True, enable TLS for the connection.
    serializer_registry:
        Registry of type→serialiser mappings. Defaults to
        :meth:`~pirn.core.transport.serializers.serializer_registry.SerializerRegistry.default`.
    """

    _key_prefix = "pirn"

    def __init__(
        self,
        *,
        host: str,
        port: int = 6379,
        ttl_sec: int = 3600,
        mode: str = "content_addressed",
        slot_name: str = "",
        cluster_mode: bool = False,
        tls: bool = False,
        serializer_registry: SerializerRegistry | None = None,
    ) -> None:
        if mode not in {"content_addressed", "write_over"}:
            raise ValueError(
                f"ValkeyTransport: mode must be 'content_addressed' or 'write_over', got {mode!r}"
            )
        if mode == "write_over" and not slot_name:
            raise ValueError("ValkeyTransport: slot_name is required when mode='write_over'")
        self._host = host
        self._port = port
        self._ttl_sec = ttl_sec
        self._mode = mode
        self._slot_name = slot_name
        self._cluster_mode = cluster_mode
        self._tls = tls
        self._registry = serializer_registry or SerializerRegistry.default()
        self._client: Any = None
        self._run_keys: dict[str, list[str]] = {}

    @property
    def transport_id(self) -> str:
        return f"valkey:{self._host}:{self._port}:{self._mode}"

    async def begin_run(self, run_id: str) -> None:
        self._client = await self._connect()
        self._run_keys[run_id] = []

    async def write(self, run_id: str, knot_id: str, value: Any) -> TransportHandle:
        if self._client is None:
            raise TransportError("ValkeyTransport: begin_run() must be called before write()")
        serialiser = self._registry.get(value)
        try:
            raw = serialiser.serialise(value)
        except Exception as exc:
            raise TransportError(
                f"ValkeyTransport: failed to serialise output of knot {knot_id!r}: {exc}"
            ) from exc
        key = self._make_key(run_id, knot_id, raw)
        try:
            if self._ttl_sec > 0:
                await self._client.set(key, raw, expiry=("EX", self._ttl_sec))
            else:
                await self._client.set(key, raw)
        except Exception as exc:
            raise TransportError(f"ValkeyTransport: failed to write key {key!r}: {exc}") from exc
        if self._mode == "content_addressed":
            self._run_keys.setdefault(run_id, []).append(key)
        type_name = f"{type(value).__module__}.{type(value).__qualname__}"
        content_hash = hashlib.sha256(raw).hexdigest()[:16]
        return TransportHandle(
            transport_id=self.transport_id,
            key=key,
            type_name=type_name,
            size_bytes=len(raw),
            checksum=content_hash,
        )

    async def read(self, handle: TransportHandle) -> Any:
        if self._client is None:
            raise TransportError("ValkeyTransport: begin_run() must be called before read()")
        try:
            raw = await self._client.get(handle.key)
        except Exception as exc:
            raise TransportError(
                f"ValkeyTransport: failed to read key {handle.key!r}: {exc}"
            ) from exc
        if raw is None:
            raise TransportError(
                f"ValkeyTransport: key {handle.key!r} not found. "
                "The value may have expired or been evicted."
            )
        serialiser = self._registry.get_by_type_name(handle.type_name)
        try:
            return serialiser.deserialise(raw, handle.type_name)
        except Exception as exc:
            raise TransportError(
                f"ValkeyTransport: cannot deserialise {handle.type_name} "
                f"from key {handle.key!r}: {exc}"
            ) from exc

    async def exists(self, handle: TransportHandle) -> bool:
        if self._client is None:
            return False
        try:
            result = await self._client.exists([handle.key])
            return bool(result)
        except Exception:
            return False

    async def end_run(self, run_id: str, *, success: bool) -> None:
        keys = self._run_keys.pop(run_id, [])
        if not keys or self._client is None:
            return
        try:
            await self._client.delete(keys)
        except Exception as exc:
            _log.warning(
                "ValkeyTransport: failed to delete %d keys for run %s: %s",
                len(keys),
                run_id,
                exc,
            )

    def _make_key(self, run_id: str, knot_id: str, raw: bytes) -> str:
        if self._mode == "write_over":
            return f"{self._key_prefix}:latest:{self._slot_name}"
        content_hash = hashlib.sha256(raw).hexdigest()[:16]
        safe_knot = knot_id.replace("/", "_").replace(":", "_")
        safe_run = run_id.replace("/", "_")
        return f"{self._key_prefix}:{safe_run}:{safe_knot}:{content_hash}"

    async def _connect(self) -> Any:
        try:
            if self._cluster_mode:
                from glide import (  # type: ignore[import-untyped]
                    GlideClusterClient,
                    GlideClusterClientConfiguration,
                    NodeAddress,
                )

                config = GlideClusterClientConfiguration(
                    addresses=[NodeAddress(host=self._host, port=self._port)],
                    use_tls=self._tls,
                )
                return await GlideClusterClient.create(config)
            else:
                from glide import (  # type: ignore[import-untyped]
                    GlideClient,
                    GlideClientConfiguration,
                    NodeAddress,
                )

                config = GlideClientConfiguration(
                    addresses=[NodeAddress(host=self._host, port=self._port)],
                    use_tls=self._tls,
                )
                return await GlideClient.create(config)
        except ImportError as exc:
            raise ImportError(
                "ValkeyTransport requires valkey-glide. Install with `pip install pirn[valkey]`."
            ) from exc
        except Exception as exc:
            raise TransportError(
                f"ValkeyTransport: failed to connect to {self._host}:{self._port}: {exc}"
            ) from exc
