"""``LoopSubTapestry.astep`` / ``afold`` — an iteration that can await (WS0).

A loop may plan or fold with ``async def``: override ``astep`` / ``afold``,
or declare ``step`` / ``fold`` themselves as coroutine functions.  The sync
pair keeps working unchanged.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.nodes.loop_sub_tapestry import LoopSubTapestry
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


class _Seed(Source):
    def __init__(self, *, value: int, **kwargs: Any) -> None:
        self._value = value
        super().__init__(**kwargs)

    async def process(self, **_: Any) -> int:
        return self._value


class _Incr(Source):
    def __init__(self, *, val: int, **kwargs: Any) -> None:
        self._val = val
        super().__init__(**kwargs)

    async def process(self, **_: Any) -> int:
        return self._val + 1


def _iteration(state: int) -> Tapestry:
    with Tapestry() as t:
        _Incr(val=state, _config=KnotConfig(id="incr"))
    return t


class _AwaitingLoop(LoopSubTapestry[int]):
    """Overrides the awaitable pair and awaits inside both."""

    def __init__(self, *, target: int, **kwargs: Any) -> None:
        self._target = target
        self.awaited: list[str] = []
        super().__init__(**kwargs)

    async def astep(self, state: int) -> tuple[Tapestry, int] | None:
        await asyncio.sleep(0)  # a backoff sleep, a budget check, ...
        self.awaited.append(f"step:{state}")
        if state >= self._target:
            return None
        return _iteration(state), state + 1

    async def afold(self, state: int, result: RunResult) -> int:
        await asyncio.sleep(0)
        self.awaited.append(f"fold:{state}")
        return result.outputs["incr"]


class _CoroutineStepLoop(LoopSubTapestry[int]):
    """Declares ``step`` / ``fold`` as coroutine functions; the defaults await them."""

    def __init__(self, *, target: int, **kwargs: Any) -> None:
        self._target = target
        super().__init__(**kwargs)

    async def step(self, state: int) -> tuple[Tapestry, int] | None:
        await asyncio.sleep(0)
        if state >= self._target:
            return None
        return _iteration(state), state + 1

    async def fold(self, state: int, result: RunResult) -> int:
        await asyncio.sleep(0)
        return result.outputs["incr"]


class _SyncLoop(LoopSubTapestry[int]):
    def __init__(self, *, target: int, **kwargs: Any) -> None:
        self._target = target
        super().__init__(**kwargs)

    def step(self, state: int) -> tuple[Tapestry, int] | None:
        if state >= self._target:
            return None
        return _iteration(state), state + 1

    def fold(self, state: int, result: RunResult) -> int:
        return result.outputs["incr"]


class _Unimplemented(LoopSubTapestry[int]):
    pass


async def test_a_loop_overriding_astep_and_afold_runs_to_completion() -> None:
    # Arrange
    with Tapestry() as t:
        seed = _Seed(value=0, _config=KnotConfig(id="seed"))
        loop = _AwaitingLoop(target=3, state=seed, _config=KnotConfig(id="loop"))

    # Act
    result = await t.run(RunRequest())

    # Assert
    assert result.succeeded
    assert result.outputs["loop"] == 3
    assert loop.awaited == [
        "step:0",
        "fold:1",
        "step:1",
        "fold:2",
        "step:2",
        "fold:3",
        "step:3",
    ]


async def test_coroutine_step_and_fold_are_awaited_by_the_defaults() -> None:
    with Tapestry() as t:
        seed = _Seed(value=0, _config=KnotConfig(id="seed"))
        _CoroutineStepLoop(target=2, state=seed, _config=KnotConfig(id="loop"))
    result = await t.run(RunRequest())
    assert result.succeeded
    assert result.outputs["loop"] == 2


async def test_sync_step_and_fold_keep_working() -> None:
    with Tapestry() as t:
        seed = _Seed(value=0, _config=KnotConfig(id="seed"))
        _SyncLoop(target=2, state=seed, _config=KnotConfig(id="loop"))
    result = await t.run(RunRequest())
    assert result.succeeded
    assert result.outputs["loop"] == 2


async def test_zero_iteration_loop_with_awaitable_step() -> None:
    with Tapestry() as t:
        seed = _Seed(value=5, _config=KnotConfig(id="seed"))
        _AwaitingLoop(target=0, state=seed, _config=KnotConfig(id="loop"))
    result = await t.run(RunRequest())
    assert result.succeeded
    assert result.outputs["loop"] == 5


async def test_default_astep_and_afold_delegate_to_the_sync_pair() -> None:
    loop = _SyncLoop.__new__(_SyncLoop)
    loop._target = 1
    assert await loop.astep(1) is None
    outcome = await loop.astep(0)
    assert outcome is not None and outcome[1] == 1


async def test_an_unimplemented_loop_names_both_forms() -> None:
    loop = _Unimplemented.__new__(_Unimplemented)
    try:
        await loop.astep(0)
    except NotImplementedError as exc:
        assert "step() or astep()" in str(exc)
    else:
        raise AssertionError("astep() should have raised NotImplementedError")
