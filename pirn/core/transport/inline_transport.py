"""``InlineTransport`` — default transport; stores values directly in the handle.

No serialisation, no I/O. The value lives in the
:class:`~pirn.core.transport.transport_handle.TransportHandle` itself so
the executor can materialise it with zero overhead. This is the backward-
compatible default: all existing knot graphs behave identically to
before the transport layer was introduced.

Size guard
----------
If a written value exceeds ``warn_above_bytes`` the transport emits a
one-time ``logging.WARNING`` per knot type suggesting the caller switch
to a storage-backed transport. This surfaces misconfiguration early
without breaking anything.

Estimating size uses ``sys.getsizeof`` which only counts the top-level
object; it deliberately under-counts containers. The intent is to catch
obviously large objects (multi-MB arrays, large DataFrames), not to
compute exact memory usage.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from pirn.core.transport.i_data_transport import IDataTransport
from pirn.core.transport.transport_handle import TransportHandle

_log = logging.getLogger(__name__)


class InlineTransport(IDataTransport):
    """Store knot outputs directly in the :class:`TransportHandle`.

    Parameters
    ----------
    warn_above_bytes:
        Emit a one-time warning when a written value's shallow size
        exceeds this threshold. Defaults to 10 MiB.
    """

    def __init__(self, *, warn_above_bytes: int = 10 * 1024 * 1024) -> None:
        self._warn_above_bytes = warn_above_bytes
        self._warned_knot_types: set[str] = set()

    @property
    def transport_id(self) -> str:
        return "inline"

    async def begin_run(self, run_id: str) -> None:
        pass

    async def write(self, run_id: str, knot_id: str, value: Any) -> TransportHandle:
        self._maybe_warn(knot_id, value)
        type_name = f"{type(value).__module__}.{type(value).__qualname__}"
        return TransportHandle(
            transport_id=self.transport_id,
            key="",
            type_name=type_name,
            size_bytes=0,
            checksum="",
            _inline_value=value,
        )

    async def read(self, handle: TransportHandle) -> Any:
        return handle._inline_value

    async def exists(self, handle: TransportHandle) -> bool:
        return handle._inline_value is not None

    async def end_run(self, run_id: str, *, success: bool) -> None:
        pass

    def _maybe_warn(self, knot_id: str, value: Any) -> None:
        if knot_id in self._warned_knot_types:
            return
        size = sys.getsizeof(value)
        if size >= self._warn_above_bytes:
            self._warned_knot_types.add(knot_id)
            _log.warning(
                "pirn.transport: knot %r produced ~%d MB via InlineTransport. "
                "Consider FilesystemTransport or ObjectStoreTransport for data of this size.",
                knot_id,
                size // (1024 * 1024),
            )
