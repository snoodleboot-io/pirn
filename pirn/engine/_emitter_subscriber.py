"""Fire-and-forget async bridge between StatusManager and an emitter."""

from __future__ import annotations

from typing import Any


class _EmitterSubscriber:
    """Schedules emitter.on_status as a fire-and-forget task per status event."""

    def __init__(self, emitter: Any, loop: Any, emitter_tasks: list) -> None:
        self._emitter = emitter
        self._loop = loop
        self._emitter_tasks = emitter_tasks

    def __call__(self, event: Any) -> None:
        task = self._loop.create_task(self.__emit_event(event))
        self._emitter_tasks.append(task)
        self._emitter_tasks[:] = [t for t in self._emitter_tasks if not t.done()]

    async def __emit_event(self, event: Any) -> None:
        try:
            await self._emitter.on_status(event)
        except Exception:
            pass
