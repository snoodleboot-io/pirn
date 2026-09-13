"""``Knot.__call__`` and cancellation (PIR-849).

A knot that raises ``asyncio.CancelledError`` itself is reporting an outcome
and becomes ``Err`` like any other exception.  A cancellation of the *task*
running the knot is not the knot's to report: it propagates, so
``asyncio.wait_for`` can raise ``TimeoutError`` and a cancelled run raises
instead of returning a failed ``RunResult``.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from pirn.core.err import Err
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.map import Map
from pirn.core.ok import Ok
from pirn.core.parameter import Parameter
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class _SelfCancelling(Knot):
    async def process(self, x: int, **_: Any) -> int:
        raise asyncio.CancelledError


class _Slow(Knot):
    async def process(self, x: int, **_: Any) -> int:
        await asyncio.sleep(10)
        return x


class _SlowSub(SubTapestry):
    async def process(self, x: int, **_: Any) -> Knot:
        p = Parameter("x", int, default=x, _config=KnotConfig(id="p"))
        return _Slow(x=p, _config=KnotConfig(id="slow"))


def _upstream() -> Parameter:
    return Parameter("x", int, default=1, _config=KnotConfig(id="up"))


async def test_a_self_raised_cancelled_error_becomes_err() -> None:
    # Arrange
    knot = _SelfCancelling(x=_upstream(), _config=KnotConfig(id="k"))

    # Act
    result = await knot({"x": 1})

    # Assert
    assert isinstance(result, Err)
    assert result.record.exc_type == "CancelledError"


async def test_a_task_cancellation_propagates_out_of_call() -> None:
    # Arrange
    knot = _Slow(x=_upstream(), _config=KnotConfig(id="k"))
    task = asyncio.create_task(knot({"x": 1}))
    await asyncio.sleep(0)

    # Act
    task.cancel()

    # Assert
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_a_timeout_around_call_raises_timeout_error() -> None:
    # Arrange: this is the property KnotConfig.timeout depends on -- a
    # swallowed cancellation would make wait_for return the Err instead.
    knot = _Slow(x=_upstream(), _config=KnotConfig(id="k"))

    # Act / Assert
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(knot({"x": 1}), timeout=0.01)


async def test_a_task_cancellation_propagates_out_of_a_fan_out() -> None:
    # Arrange
    knot = _Slow(x=Map(_upstream()), _config=KnotConfig(id="k"))
    task = asyncio.create_task(knot({"x": [1, 2, 3]}))
    await asyncio.sleep(0)

    # Act
    task.cancel()

    # Assert
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_a_task_cancellation_propagates_out_of_a_sub_tapestry() -> None:
    # Arrange
    with Tapestry():
        sub = _SlowSub(x=_upstream(), _config=KnotConfig(id="sub"))
    task = asyncio.create_task(sub({"x": 1}))
    await asyncio.sleep(0.01)

    # Act
    task.cancel()

    # Assert
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_an_ordinary_exception_is_still_an_err() -> None:
    # Arrange
    class _Boom(Knot):
        async def process(self, x: int, **_: Any) -> int:
            raise RuntimeError("boom")

    knot = _Boom(x=_upstream(), _config=KnotConfig(id="k"))

    # Act
    result = await knot({"x": 1})

    # Assert
    assert isinstance(result, Err)
    assert result.record.exc_type == "RuntimeError"


async def test_a_successful_call_is_unaffected() -> None:
    # Arrange
    class _Double(Knot):
        async def process(self, x: int, **_: Any) -> int:
            return x * 2

    knot = _Double(x=_upstream(), _config=KnotConfig(id="k"))

    # Act
    result = await knot({"x": 2})

    # Assert
    assert result == Ok(value=4)


def test_is_task_cancellation_ignores_other_exceptions() -> None:
    assert not Knot._is_task_cancellation(RuntimeError("x"))


def test_is_task_cancellation_is_false_outside_a_task() -> None:
    assert not Knot._is_task_cancellation(asyncio.CancelledError())
