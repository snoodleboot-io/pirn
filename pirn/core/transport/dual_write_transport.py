"""``DualWriteTransport`` — writes to two transports simultaneously.

Every :meth:`write` call fans out to both *primary* and *mirror* transports
concurrently.  Reads are always served from *primary*.  This is useful for:

- Keeping a fast local copy (primary) while archiving to object storage (mirror)
- Zero-downtime migration between two transport backends
- Audit copies: every knot output goes to both a ValkeyTransport and a
  FilesystemTransport for debugging

The executor sees a single transport; DualWriteTransport handles lifecycle
(``begin_run`` / ``end_run``) for both backends.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pirn.core.transport.data_transport import DataTransport
from pirn.core.transport.transport_error import TransportError
from pirn.core.transport.transport_handle import TransportHandle

_log = logging.getLogger(__name__)


class DualWriteTransport(DataTransport):
    """Write to *primary* and *mirror* concurrently; read from *primary*.

    Parameters
    ----------
    primary:
        The authoritative transport.  All reads are served from here.
    mirror:
        The secondary transport that receives a copy of every write.
    mirror_errors:
        ``"raise"`` — propagate mirror failures (default).
        ``"warn"``  — log a warning and continue if the mirror write fails.
        ``"ignore"`` — silently swallow mirror errors.
    """

    def __init__(
        self,
        *,
        primary: DataTransport,
        mirror: DataTransport,
        mirror_errors: str = "raise",
    ) -> None:
        if mirror_errors not in ("raise", "warn", "ignore"):
            raise ValueError(
                f"DualWriteTransport: mirror_errors must be 'raise', 'warn', or 'ignore', "
                f"got {mirror_errors!r}"
            )
        self._primary = primary
        self._mirror = mirror
        self._mirror_errors = mirror_errors

    @property
    def transport_id(self) -> str:
        return f"dual:{self._primary.transport_id}+{self._mirror.transport_id}"

    async def begin_run(self, run_id: str) -> None:
        await asyncio.gather(
            self._primary.begin_run(run_id),
            self._mirror.begin_run(run_id),
        )

    async def write(self, run_id: str, knot_id: str, value: Any) -> TransportHandle:
        primary_task = asyncio.ensure_future(self._primary.write(run_id, knot_id, value))
        mirror_task = asyncio.ensure_future(self._mirror.write(run_id, knot_id, value))

        results = await asyncio.gather(primary_task, mirror_task, return_exceptions=True)
        primary_result, mirror_result = results

        if isinstance(primary_result, BaseException):
            raise primary_result

        if isinstance(mirror_result, BaseException):
            self._handle_mirror_error(
                f"DualWriteTransport: mirror write failed for knot {knot_id!r}: {mirror_result}",
                mirror_result,
            )

        return primary_result

    async def read(self, handle: TransportHandle) -> Any:
        return await self._primary.read(handle)

    async def exists(self, handle: TransportHandle) -> bool:
        return await self._primary.exists(handle)

    async def end_run(self, run_id: str, *, success: bool) -> None:
        results = await asyncio.gather(
            self._primary.end_run(run_id, success=success),
            self._mirror.end_run(run_id, success=success),
            return_exceptions=True,
        )
        errors = [r for r in results if isinstance(r, BaseException)]
        if errors:
            raise TransportError(
                f"DualWriteTransport: end_run errors: {'; '.join(str(e) for e in errors)}"
            )

    def _handle_mirror_error(self, message: str, exc: BaseException) -> None:
        if self._mirror_errors == "raise":
            raise TransportError(message) from exc
        if self._mirror_errors == "warn":
            _log.warning(message)
