"""Direct tests for the shared :class:`AsyncFanoutEngine` per-item mechanics.

The base is exercised end-to-end through ``ParallelToolExecutor`` and ``MapAgent``,
but as a shared primitive its retry/timeout/hook contract is pinned here against a
minimal subclass, independent of either engine's scheduling.
"""

from __future__ import annotations

import asyncio

import pytest

from pirn_agents.async_fanout_engine import AsyncFanoutEngine
from pirn_agents.llm.retry_policy import RetryPolicy


class _Engine(AsyncFanoutEngine[str]):
    """Minimal concrete engine wiring only the mixin's required attributes."""

    def __init__(self) -> None:
        self._retry_policy = RetryPolicy(base_delay=0.0)
        self._rng = None
        self._sleep = asyncio.sleep


def _builders() -> dict[str, object]:
    return {
        "on_ok": lambda value, attempts: f"ok:{value}:{attempts}",
        "on_timeout": lambda attempts: f"timeout:{attempts}",
        "on_error": lambda exc, attempts: f"error:{exc}:{attempts}",
    }


class TestRunWithRetries:
    async def test_success_first_try(self) -> None:
        async def _invoke() -> object:
            return "v"

        result = await _Engine()._run_with_retries(_invoke, timeout=None, retries=2, **_builders())
        assert result == "ok:v:1"

    async def test_retries_then_succeeds(self) -> None:
        calls = 0

        async def _invoke() -> object:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise RuntimeError("flaky")
            return "v"

        result = await _Engine()._run_with_retries(_invoke, timeout=None, retries=2, **_builders())
        assert result == "ok:v:3"  # attempts counts the successful try

    async def test_exhausts_retries_to_error(self) -> None:
        async def _invoke() -> object:
            raise RuntimeError("boom")

        result = await _Engine()._run_with_retries(_invoke, timeout=None, retries=1, **_builders())
        assert result == "error:boom:2"  # initial + 1 retry

    async def test_timeout_is_terminal_not_retried(self) -> None:
        attempts = 0

        async def _invoke() -> object:
            nonlocal attempts
            attempts += 1
            await asyncio.sleep(1)
            return "never"

        result = await _Engine()._run_with_retries(_invoke, timeout=0.01, retries=5, **_builders())
        assert result == "timeout:1"
        assert attempts == 1  # a timeout is never retried

    async def test_timeouterror_is_retryable_when_no_budget(self) -> None:
        # Without a timeout budget, a raw TimeoutError is just another exception.
        calls = 0

        async def _invoke() -> object:
            nonlocal calls
            calls += 1
            if calls < 2:
                raise TimeoutError("transient")
            return "v"

        result = await _Engine()._run_with_retries(_invoke, timeout=None, retries=2, **_builders())
        assert result == "ok:v:2"

    async def test_hooks_fire_in_order(self) -> None:
        events: list[str] = []

        async def _invoke() -> object:
            events.append("invoke")
            if len(events) < 3:  # before_attempt + invoke, then fails first round
                raise RuntimeError("x")
            return "v"

        async def _before() -> None:
            events.append("before")

        result = await _Engine()._run_with_retries(
            _invoke,
            timeout=None,
            retries=3,
            before_attempt=_before,
            on_exception=lambda exc: events.append(f"exc:{exc}"),
            on_success=lambda: events.append("success"),
            **_builders(),
        )
        assert result.startswith("ok:")
        # before precedes each invoke; on_exception fires per failure; success once.
        assert events[0] == "before"
        assert events.count("before") == 2
        assert "exc:x" in events
        assert events[-1] == "success"

    async def test_cancelled_error_propagates(self) -> None:
        async def _invoke() -> object:
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await _Engine()._run_with_retries(_invoke, timeout=None, retries=3, **_builders())


class TestDrainOnCancel:
    async def test_cancels_and_awaits_every_task(self) -> None:
        started = asyncio.Event()

        async def _long() -> str:
            started.set()
            await asyncio.sleep(10)
            return "done"

        tasks = [asyncio.ensure_future(_long()) for _ in range(3)]
        await started.wait()

        await _Engine()._drain_on_cancel(tasks)

        assert all(task.cancelled() for task in tasks)
