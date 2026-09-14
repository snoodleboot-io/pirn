"""Fire-and-forget async bridge between StatusManager and an emitter."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from pirn.emitters.emitter import Emitter
    from pirn.emitters.emitter_error_policy import EmitterErrorPolicy
    from pirn.managers.status_event import StatusEvent

#: Signature of ``EmitterFanout.handle_emitter_error`` — kept as a type alias so
#: ``EmitterSubscriber`` does not need to import ``EmitterFanout`` (which would be
#: circular: ``emitter_fanout.py`` imports this module).
EmitterErrorHandler: TypeAlias = Callable[["Emitter", str, Exception, "EmitterErrorPolicy"], None]


class EmitterSubscriber:
    """Schedules emitter.on_status as a fire-and-forget task per status event."""

    def __init__(
        self,
        emitter: Emitter,
        loop: asyncio.AbstractEventLoop,
        emitter_tasks: list[asyncio.Task[None]],
        error_policy: EmitterErrorPolicy,
        on_error: EmitterErrorHandler,
    ) -> None:
        self._emitter = emitter
        self._loop = loop
        self._emitter_tasks = emitter_tasks
        self._error_policy = error_policy
        self._on_error = on_error

    def __call__(self, event: StatusEvent) -> None:
        task = self._loop.create_task(self.__emit_event(event))
        self._emitter_tasks.append(task)
        self._emitter_tasks[:] = [t for t in self._emitter_tasks if not t.done()]

    async def __emit_event(self, event: StatusEvent) -> None:
        try:
            await self._emitter.on_status(event)
        except Exception as exc:
            # Routed through the same IGNORE/WARN/RAISE dispatch used for
            # on_lineage/on_run_result (EmitterFanout.handle_emitter_error), so a
            # broken on_status emitter is reported the same way every other
            # emitter failure is instead of being swallowed unconditionally.
            # RAISE here still cannot fail this run synchronously — this
            # task is fire-and-forget and nothing awaits it — but letting
            # the exception propagate out of the task body surfaces it via
            # asyncio's "exception was never retrieved" reporting instead of
            # disappearing silently.
            self._on_error(self._emitter, "on_status", exc, self._error_policy)
