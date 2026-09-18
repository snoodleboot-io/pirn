"""Async bridge between StatusManager and an emitter's ``on_status``."""

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
    """Schedules ``emitter.on_status`` as a task per status event.

    ``StatusManager`` calls its subscribers synchronously from inside the
    engine's scheduling loop, so the async hook cannot be awaited in place.
    Each event's delivery runs as a task held in the run's
    ``RunContext.emitter_tasks``; the engine awaits every one of them before
    the run finishes (``EmitterFanout.drain_status_deliveries``), so a hook
    that raised under ``EmitterErrorPolicy.RAISE`` fails the run instead of
    being dropped with the loop.

    Algorithm:
        1. On each event, create the delivery task and append it to the
           shared task list.
        2. Prune tasks that already finished cleanly; a task that finished
           with an exception stays until the engine drains it, so the
           failure is never lost to the pruning.
        3. Inside the task, route an exception through the run's policy:
           ``IGNORE`` and ``WARN`` handle it there, ``RAISE`` re-raises it so
           the task completes with it.
    """

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
        self._emitter_tasks[:] = [
            t for t in self._emitter_tasks if not EmitterSubscriber._finished_cleanly(t)
        ]

    @staticmethod
    def _finished_cleanly(task: asyncio.Task[None]) -> bool:
        """Whether *task* is done without an exception the engine still has to see."""
        if not task.done():
            return False
        if task.cancelled():
            return True
        return task.exception() is None

    async def __emit_event(self, event: StatusEvent) -> None:
        try:
            await self._emitter.on_status(event)
        except Exception as exc:
            # Routed through the same IGNORE/WARN/RAISE dispatch used for
            # on_knot_result/on_lineage/on_run_result. Under RAISE the
            # exception propagates out of this task and the engine re-raises
            # it when it drains the run's delivery tasks.
            self._on_error(self._emitter, "on_status", exc, self._error_policy)
