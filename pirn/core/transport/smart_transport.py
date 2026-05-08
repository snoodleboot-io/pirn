"""``SmartTransport`` — routes writes to one of two transports based on size and type.

For small values (below *threshold_bytes*) data stays in the fast transport
(default: ``InlineTransport``).  Large values, or values whose type matches
*large_type_patterns*, are routed to the slow/bulk transport (default:
``FilesystemTransport``).

The split is transparent to knots and to the executor: ``read`` is always
routed to whichever transport produced the handle (recorded in
``TransportHandle.transport_id``).
"""

from __future__ import annotations

import logging
import pickle
from typing import Any

from pirn.core.transport.data_transport import DataTransport
from pirn.core.transport.serializers.serializer_registry import SerializerRegistry
from pirn.core.transport.transport_handle import TransportHandle

_log = logging.getLogger(__name__)

_DEFAULT_THRESHOLD = 1024 * 1024  # 1 MiB


class SmartTransport(DataTransport):
    """Route writes to *fast* or *bulk* transport based on serialised size.

    Parameters
    ----------
    fast:
        Transport used for values whose serialised size is below
        *threshold_bytes*.  Defaults to ``InlineTransport``.
    bulk:
        Transport used for values at or above *threshold_bytes*.
        Defaults to ``FilesystemTransport`` in a system temp directory.
    threshold_bytes:
        Byte boundary that governs routing.  Defaults to 1 MiB.
    large_types:
        Additional Python types always routed to *bulk* regardless of size
        (e.g. ``numpy.ndarray``, ``pandas.DataFrame``).  Checked with
        ``isinstance``; evaluation is order-insensitive.
    serializer_registry:
        Used to measure the serialised size of a value before writing.
        If ``None``, falls back to ``pickle.dumps`` for the size probe —
        this is only used for routing; the transports do their own
        serialisation.
    """

    def __init__(
        self,
        *,
        fast: DataTransport | None = None,
        bulk: DataTransport | None = None,
        threshold_bytes: int = _DEFAULT_THRESHOLD,
        large_types: tuple[type, ...] = (),
        serializer_registry: SerializerRegistry | None = None,
    ) -> None:
        from pirn.core.transport.inline_transport import InlineTransport

        self._fast: DataTransport = fast or InlineTransport()
        self._bulk: DataTransport
        if bulk is not None:
            self._bulk = bulk
        else:
            import tempfile
            from pathlib import Path

            from pirn.core.transport.filesystem_transport import FilesystemTransport

            self._bulk = FilesystemTransport(base_dir=Path(tempfile.gettempdir()) / "pirn-smart")
        self._threshold = threshold_bytes
        self._large_types = large_types
        self._registry = serializer_registry

    @property
    def transport_id(self) -> str:
        return f"smart:{self._fast.transport_id}|{self._bulk.transport_id}"

    async def begin_run(self, run_id: str) -> None:
        await self._fast.begin_run(run_id)
        await self._bulk.begin_run(run_id)

    async def write(self, run_id: str, knot_id: str, value: Any) -> TransportHandle:
        transport = self._route(value)
        return await transport.write(run_id, knot_id, value)

    async def read(self, handle: TransportHandle) -> Any:
        transport = self._transport_for_handle(handle)
        return await transport.read(handle)

    async def exists(self, handle: TransportHandle) -> bool:
        transport = self._transport_for_handle(handle)
        return await transport.exists(handle)

    async def end_run(self, run_id: str, *, success: bool) -> None:
        await self._fast.end_run(run_id, success=success)
        await self._bulk.end_run(run_id, success=success)

    def _route(self, value: Any) -> DataTransport:
        if self._large_types and isinstance(value, self._large_types):
            return self._bulk
        size = self._probe_size(value)
        if size >= self._threshold:
            _log.debug("SmartTransport: routing %d bytes to bulk transport", size)
            return self._bulk
        return self._fast

    def _probe_size(self, value: Any) -> int:
        if self._registry is not None:
            try:
                serialiser = self._registry.get(value)
                return len(serialiser.serialise(value))
            except Exception:
                pass
        try:
            return len(pickle.dumps(value, protocol=5))
        except Exception:
            return 0

    def _transport_for_handle(self, handle: TransportHandle) -> DataTransport:
        fast_id = self._fast.transport_id
        bulk_id = self._bulk.transport_id
        if handle.transport_id == fast_id:
            return self._fast
        if handle.transport_id == bulk_id:
            return self._bulk
        raise ValueError(
            f"SmartTransport: handle transport_id {handle.transport_id!r} matches neither "
            f"fast ({fast_id!r}) nor bulk ({bulk_id!r})"
        )
