"""Unit tests for EmitterSubscriber routing on_status failures through policy (PIR-856)."""

from __future__ import annotations

import asyncio
import unittest
from typing import Any

from pirn.emitters.emitter_error_policy import EmitterErrorPolicy
from pirn.engine.emitter_fanout import EmitterFanout
from pirn.engine.emitter_subscriber import EmitterSubscriber


class _FailingEmitter:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def on_status(self, event: Any) -> None:
        raise self._exc


async def _run_and_collect(subscriber: EmitterSubscriber, event: Any) -> list[asyncio.Task]:
    """Invoke *subscriber* the way StatusManager does, then await its task."""
    tasks: list[asyncio.Task] = []
    subscriber(event)
    tasks = list(subscriber._emitter_tasks)
    await asyncio.gather(*tasks, return_exceptions=True)
    return tasks


class TestEmitterSubscriberErrorRouting(unittest.IsolatedAsyncioTestCase):
    async def test_ignore_policy_swallows_on_status_failure(self) -> None:
        # Arrange
        calls: list[tuple[Any, str, Exception, EmitterErrorPolicy]] = []
        emitter = _FailingEmitter(RuntimeError("boom"))
        subscriber = EmitterSubscriber(
            emitter,
            asyncio.get_running_loop(),
            [],
            EmitterErrorPolicy.IGNORE,
            lambda *args: calls.append(args),
        )

        # Act
        tasks = await _run_and_collect(subscriber, event="e")

        # Assert: on_error was invoked (routed), but IGNORE means no side effect beyond that.
        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0][3], EmitterErrorPolicy.IGNORE)
        self.assertIsNone(tasks[0].exception())

    async def test_warn_policy_is_routed_through_handle_emitter_error(self) -> None:
        # Arrange
        emitter = _FailingEmitter(RuntimeError("boom"))
        subscriber = EmitterSubscriber(
            emitter,
            asyncio.get_running_loop(),
            [],
            EmitterErrorPolicy.WARN,
            EmitterFanout.handle_emitter_error,
        )

        # Act / Assert: WARN logs rather than raising back into the task.
        with self.assertLogs("pirn.engine.emitter_fanout", level="WARNING") as ctx:
            tasks = await _run_and_collect(subscriber, event="e")
        self.assertTrue(any("on_status" in msg for msg in ctx.output))
        self.assertIsNone(tasks[0].exception())

    async def test_raise_policy_propagates_out_of_the_fire_and_forget_task(self) -> None:
        """RAISE cannot fail the run synchronously (nothing awaits this task),

        but it must no longer be swallowed: the task itself completes with
        the original exception, visible via ``task.exception()``, instead of
        silently succeeding the way an unconditional ``except: pass`` would.
        """
        # Arrange
        boom = RuntimeError("boom")
        emitter = _FailingEmitter(boom)
        subscriber = EmitterSubscriber(
            emitter,
            asyncio.get_running_loop(),
            [],
            EmitterErrorPolicy.RAISE,
            EmitterFanout.handle_emitter_error,
        )

        # Act
        tasks = await _run_and_collect(subscriber, event="e")

        # Assert
        self.assertIs(tasks[0].exception(), boom)

    async def test_successful_on_status_never_calls_the_error_handler(self) -> None:
        # Arrange
        calls: list[Any] = []

        class _OkEmitter:
            async def on_status(self, event: Any) -> None:
                return None

        subscriber = EmitterSubscriber(
            _OkEmitter(),
            asyncio.get_running_loop(),
            [],
            EmitterErrorPolicy.RAISE,
            lambda *args: calls.append(args),
        )

        # Act
        tasks = await _run_and_collect(subscriber, event="e")

        # Assert
        self.assertEqual(calls, [])
        self.assertIsNone(tasks[0].exception())


if __name__ == "__main__":
    unittest.main()
