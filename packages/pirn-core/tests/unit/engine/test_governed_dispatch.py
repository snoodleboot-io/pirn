"""Unit tests for ``GovernedDispatch`` (ADR agents-speaks-core, WS0).

A scripted dispatcher returns a fixed sequence of results so every branch of
the timeout/retry loop is exercised without a real tapestry, and an injected
sleep records the backoff the loop asked for instead of waiting.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import pytest

from pirn.core.err import Err
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_retry_policy import KnotRetryPolicy
from pirn.core.ok import Ok
from pirn.core.result import Result
from pirn.core.skipped import Skipped
from pirn.engine.admission.admission import Admission
from pirn.engine.admission.admission_ticket import AdmissionTicket
from pirn.engine.admission.admission_ticket_holder import AdmissionTicketHolder
from pirn.engine.dispatchers.dispatcher import Dispatcher
from pirn.engine.governed_dispatch import GovernedDispatch
from pirn.managers.exception_record import ExceptionRecord


class _Scripted(Dispatcher):
    """Returns the scripted results in order; a ``float`` entry sleeps that long first."""

    def __init__(self, script: list[Result[Any] | float]) -> None:
        self.script = list(script)
        self.calls = 0

    @property
    def name(self) -> str:
        return "Scripted"

    async def dispatch(self, knot: Knot, inputs: Mapping[str, Any]) -> Result[Any]:
        self.calls += 1
        entry = self.script.pop(0)
        if isinstance(entry, int | float):
            await asyncio.sleep(entry)
            return Ok(value="late")
        return entry


class _Noop(Knot):
    async def process(self, **_: Any) -> str:
        return "unused"


def _err(exc_type: str = "RuntimeError") -> Err:
    return Err(record=ExceptionRecord.for_knot("k", type(exc_type, (Exception,), {})("boom")))


def _knot(**config: Any) -> Knot:
    return _Noop(_config=KnotConfig(id="k", **config))


class _Sleeps:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


class _FakeGate(Admission):
    """Records release/admit calls in order; always admits, never blocks."""

    def __init__(self) -> None:
        self.events: list[str] = []

    def has_capacity(self) -> bool:
        return True

    def try_admit(self, knot: Knot) -> AdmissionTicket:
        self.events.append("admit")
        return AdmissionTicket(knot_id=knot.knot_id)

    def release(self, ticket: AdmissionTicket) -> None:
        self.events.append("release")

    async def wait_for_release(self) -> None:
        return None

    def current_limit(self, group: str | None) -> int | None:
        return None

    def set_limit(self, group: str | None, limit: int) -> None:
        raise NotImplementedError


async def test_without_policy_one_attempt_passes_through() -> None:
    # Arrange
    dispatcher = _Scripted([Ok(value=1)])
    governed = GovernedDispatch(dispatcher)

    # Act
    result, attempts = await governed.dispatch(_knot(), {})

    # Assert
    assert result == Ok(value=1)
    assert attempts == 1
    assert dispatcher.calls == 1


async def test_without_policy_an_err_is_not_retried() -> None:
    dispatcher = _Scripted([_err(), Ok(value=1)])
    result, attempts = await GovernedDispatch(dispatcher).dispatch(_knot(), {})
    assert isinstance(result, Err)
    assert attempts == 1


async def test_timeout_becomes_err_knot_timeout_error() -> None:
    # Arrange
    dispatcher = _Scripted([10.0])
    governed = GovernedDispatch(dispatcher)

    # Act
    result, attempts = await governed.dispatch(_knot(timeout=0.01), {})

    # Assert
    assert isinstance(result, Err)
    assert result.record.exc_type == "KnotTimeoutError"
    assert "'k'" in result.record.message
    assert attempts == 1


async def test_a_fast_attempt_is_unaffected_by_the_timeout() -> None:
    result, _ = await GovernedDispatch(_Scripted([Ok(value=2)])).dispatch(_knot(timeout=5.0), {})
    assert result == Ok(value=2)


async def test_retry_redispatches_after_backoff_until_ok() -> None:
    # Arrange
    dispatcher = _Scripted([_err(), _err(), Ok(value=3)])
    sleeps = _Sleeps()
    policy = KnotRetryPolicy(max_attempts=5, base_delay=0.1, multiplier=2.0, jitter=False)
    governed = GovernedDispatch(dispatcher, sleep=sleeps)

    # Act
    result, attempts = await governed.dispatch(_knot(retry=policy), {})

    # Assert
    assert result == Ok(value=3)
    assert attempts == 3
    assert sleeps.delays == [0.1, 0.2]


async def test_retry_returns_the_last_err_once_spent() -> None:
    # Arrange
    dispatcher = _Scripted([_err("A"), _err("B"), _err("C")])
    sleeps = _Sleeps()
    policy = KnotRetryPolicy(max_attempts=3, jitter=False)

    # Act
    result, attempts = await GovernedDispatch(dispatcher, sleep=sleeps).dispatch(
        _knot(retry=policy), {}
    )

    # Assert
    assert isinstance(result, Err)
    assert result.record.exc_type == "C"
    assert attempts == 3
    assert len(sleeps.delays) == 2
    assert dispatcher.script == []


async def test_a_non_retryable_failure_is_returned_at_once() -> None:
    # Arrange
    dispatcher = _Scripted([_err("ValueError"), Ok(value=1)])
    sleeps = _Sleeps()
    policy = KnotRetryPolicy(max_attempts=3, is_retryable=lambda r: r.exc_type != "ValueError")

    # Act
    result, attempts = await GovernedDispatch(dispatcher, sleep=sleeps).dispatch(
        _knot(retry=policy), {}
    )

    # Assert
    assert isinstance(result, Err)
    assert attempts == 1
    assert sleeps.delays == []


async def test_a_retry_after_hint_sets_the_sleep() -> None:
    dispatcher = _Scripted([_err(), Ok(value=1)])
    sleeps = _Sleeps()
    policy = KnotRetryPolicy(max_attempts=2, retry_after=lambda r: 0.7, max_retry_after=5.0)
    await GovernedDispatch(dispatcher, sleep=sleeps).dispatch(_knot(retry=policy), {})
    assert sleeps.delays == [0.7]


async def test_jitter_uses_the_injected_rng() -> None:
    dispatcher = _Scripted([_err(), Ok(value=1)])
    sleeps = _Sleeps()
    policy = KnotRetryPolicy(max_attempts=2, base_delay=1.0, jitter=True)
    await GovernedDispatch(dispatcher, sleep=sleeps, rng=lambda: 0.5).dispatch(
        _knot(retry=policy), {}
    )
    assert sleeps.delays == [0.5]


async def test_a_timed_out_attempt_is_retried() -> None:
    # Arrange
    dispatcher = _Scripted([10.0, Ok(value="second")])
    sleeps = _Sleeps()
    policy = KnotRetryPolicy(max_attempts=2, jitter=False)

    # Act
    result, attempts = await GovernedDispatch(dispatcher, sleep=sleeps).dispatch(
        _knot(timeout=0.01, retry=policy), {}
    )

    # Assert
    assert result == Ok(value="second")
    assert attempts == 2


async def test_a_skipped_result_is_never_retried() -> None:
    dispatcher = _Scripted([Skipped(reason="gate_closed"), Ok(value=1)])
    policy = KnotRetryPolicy(max_attempts=3)
    result, attempts = await GovernedDispatch(dispatcher).dispatch(_knot(retry=policy), {})
    assert isinstance(result, Skipped)
    assert attempts == 1


async def test_a_cancellation_during_backoff_propagates() -> None:
    # Arrange: the sleep is a real one long enough to be cancelled mid-way.
    dispatcher = _Scripted([_err(), Ok(value=1)])
    policy = KnotRetryPolicy(max_attempts=2, base_delay=10.0, jitter=False)
    task = asyncio.create_task(GovernedDispatch(dispatcher).dispatch(_knot(retry=policy), {}))
    await asyncio.sleep(0.01)

    # Act
    task.cancel()

    # Assert
    with pytest.raises(asyncio.CancelledError):
        await task
    assert dispatcher.calls == 1


def test_exposes_the_wrapped_dispatcher() -> None:
    dispatcher = _Scripted([])
    assert GovernedDispatch(dispatcher).dispatcher is dispatcher


class _Container(Knot):
    """A stand-in for SubTapestry/LoopSubTapestry: holds no admission slot."""

    _holds_admission_slot = False

    async def process(self, **_: Any) -> str:
        return "unused"


class _RoutingDispatcher(Dispatcher):
    """Records which dispatcher instance a knot actually ran on."""

    def __init__(self) -> None:
        self.container_dispatcher = _Scripted([Ok(value="container")])
        self.calls: list[str] = []

    @property
    def name(self) -> str:
        return "Routing"

    async def dispatch(self, knot: Knot, inputs: Mapping[str, Any]) -> Result[Any]:
        self.calls.append("leaf")
        return Ok(value="leaf")

    def dispatcher_for_container(self, knot: Knot) -> Dispatcher:
        self.calls.append("container")
        return self.container_dispatcher


async def test_a_leaf_knot_dispatches_on_the_wrapped_dispatcher() -> None:
    dispatcher = _RoutingDispatcher()
    result, _ = await GovernedDispatch(dispatcher).dispatch(_knot(), {})
    assert result == Ok(value="leaf")
    assert dispatcher.calls == ["leaf"]
    assert dispatcher.container_dispatcher.calls == 0


async def test_a_container_knot_dispatches_on_dispatcher_for_container() -> None:
    # Arrange (PIR-870): a container must run on whatever
    # ``dispatcher_for_container`` returns, not the wrapped dispatcher
    # itself -- ``ThreadDispatcher`` uses this to keep a container off its
    # pool workers.
    dispatcher = _RoutingDispatcher()
    container = _Container(_config=KnotConfig(id="c"))

    # Act
    result, _ = await GovernedDispatch(dispatcher).dispatch(container, {})

    # Assert
    assert result == Ok(value="container")
    assert dispatcher.calls == ["container"]
    assert dispatcher.container_dispatcher.calls == 1


async def test_retry_releases_the_slot_for_backoff_and_readmits_before_the_next_attempt() -> None:
    # Arrange (PIR-870): a sleeping retry must not hold a slot -- release
    # before the sleep, re-admit before the next attempt.
    dispatcher = _Scripted([_err(), Ok(value=1)])
    sleeps = _Sleeps()
    policy = KnotRetryPolicy(max_attempts=2, base_delay=0.1, jitter=False)
    gate = _FakeGate()
    knot = _knot(retry=policy)
    holder = AdmissionTicketHolder(AdmissionTicket(knot_id=knot.knot_id))
    original_ticket = holder.ticket

    # Act
    result, attempts = await GovernedDispatch(dispatcher, sleep=sleeps).dispatch(
        knot, {}, gate=gate, ticket_holder=holder
    )

    # Assert
    assert result == Ok(value=1)
    assert attempts == 2
    assert gate.events == ["release", "admit"]
    assert sleeps.delays == [0.1]
    # The holder now names the freshly re-admitted ticket, not the one it
    # started with -- the engine reads this back to release the right one.
    assert holder.ticket is not original_ticket


async def test_a_slot_free_container_ticket_is_never_touched_during_backoff() -> None:
    # Arrange: a container's ticket (``held=False``) holds no slot at all,
    # so there is nothing to release or re-admit -- it just sleeps.
    dispatcher = _Scripted([_err(), Ok(value=1)])
    sleeps = _Sleeps()
    policy = KnotRetryPolicy(max_attempts=2, base_delay=0.1, jitter=False)
    gate = _FakeGate()
    knot = _knot(retry=policy)
    holder = AdmissionTicketHolder(AdmissionTicket(knot_id=knot.knot_id, held=False))

    # Act
    result, attempts = await GovernedDispatch(dispatcher, sleep=sleeps).dispatch(
        knot, {}, gate=gate, ticket_holder=holder
    )

    # Assert
    assert result == Ok(value=1)
    assert attempts == 2
    assert gate.events == []
    assert holder.ticket.held is False


async def test_without_a_ticket_holder_backoff_just_sleeps() -> None:
    # Arrange: a caller that passes no gate/holder (e.g. a direct unit test
    # of this class) keeps the old sleep-only behaviour.
    dispatcher = _Scripted([_err(), Ok(value=1)])
    sleeps = _Sleeps()
    policy = KnotRetryPolicy(max_attempts=2, base_delay=0.1, jitter=False)

    # Act
    result, attempts = await GovernedDispatch(dispatcher, sleep=sleeps).dispatch(
        _knot(retry=policy), {}
    )

    # Assert
    assert result == Ok(value=1)
    assert attempts == 2
    assert sleeps.delays == [0.1]
