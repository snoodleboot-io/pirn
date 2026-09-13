"""The engine's admission-queue scheduler (PIR-841 slice 1).

The engine used to run a graph in waves: dispatch every ready knot, wait for
*all* of them, then look for the next ready set.  It now schedules a knot the
moment its own parents resolve.  These tests pin the two defects that fixes
(a child held back by its parent's slow sibling; a fast knot's ``finished_at``
stamped when a slower sibling finished) and the guarantee the rewrite must
keep: per-knot records are reported in an order that depends on the graph,
never on which knot happened to finish first.

Choreography uses ``asyncio.Event``s rather than sleeps wherever an ordering
is asserted, and every run is wrapped in a timeout: under the old wave loop the
event-gated scenarios below deadlock instead of passing slowly.
"""

from __future__ import annotations

import asyncio
import contextvars
import itertools
import threading
from collections import defaultdict
from typing import Any

import pytest

from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.tapestry import Tapestry, _current_run_id, current_run_id


class _Script:
    """Choreography shared by the scripted knots of one run.

    Records ``start:<id>`` / ``finish:<id>`` (and ``cancelled:<id>``) in the
    order they happen, and lets a test make a knot wait on a barrier or a
    named event, sleep, or fail.
    """

    def __init__(self) -> None:
        self.log: list[str] = []
        self.waits: dict[str, str] = {}
        self.delays: dict[str, float] = {}
        self.failures: set[str] = set()
        self.barrier: asyncio.Barrier | None = None
        self.cleanup_s: float | None = None
        self.run_id: str | None = None
        self._events: defaultdict[str, asyncio.Event] = defaultdict(asyncio.Event)

    def event(self, name: str) -> asyncio.Event:
        return self._events[name]

    async def play(self, knot_id: str) -> str:
        self.run_id = current_run_id()
        self.log.append(f"start:{knot_id}")
        self.event(f"started:{knot_id}").set()
        try:
            if self.barrier is not None:
                await self.barrier.wait()
            if knot_id in self.waits:
                await self.event(self.waits[knot_id]).wait()
            if knot_id in self.delays:
                await asyncio.sleep(self.delays[knot_id])
        except asyncio.CancelledError:
            self.log.append(f"cancelled:{knot_id}")
            self.event(f"cancelled:{knot_id}").set()
            if self.cleanup_s is not None:
                # Cleanup that itself awaits, like closing a connection.
                await asyncio.sleep(self.cleanup_s)
            self.log.append(f"cleaned:{knot_id}")
            raise
        self.log.append(f"finish:{knot_id}")
        self.event(f"finished:{knot_id}").set()
        if knot_id in self.failures:
            raise ValueError(f"{knot_id} failed on purpose")
        return knot_id


class _Scripted(Knot):
    """A knot whose behaviour is dictated by a ``_Script``."""

    def __init__(self, *, script: _Script, **kwargs: Any) -> None:
        self._script = script
        super().__init__(**kwargs)

    async def process(self, **_inputs: Any) -> str:
        return await self._script.play(self.knot_id)


class _Registrar(Knot):
    """Registers ``_Scripted(x=<late_parent>)`` as ``late`` mid-run.

    After registering it sets ``registered`` and then waits for the script
    event named by ``hold_until`` (if any) before finishing.
    """

    def __init__(
        self,
        *,
        script: _Script,
        target: Tapestry,
        late_parent: Knot,
        hold_until: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._script = script
        self._target = target
        self._late_parent = late_parent
        self._hold_until = hold_until
        super().__init__(**kwargs)

    async def process(self, **_inputs: Any) -> str:
        with self._target:
            _Scripted(x=self._late_parent, script=self._script, _config=KnotConfig(id="late"))
        self._script.event("registered").set()
        if self._hold_until is not None:
            await self._script.event(self._hold_until).wait()
            # Let the engine process the completion that released us first,
            # so the newcomer is absorbed there rather than at our own.
            await asyncio.sleep(0.05)
        return self.knot_id


def _register_late_parentless(script: _Script, target: Tapestry, run_id: str | None) -> None:
    """Register a parentless ``late`` knot with *run_id* as the ambient run.

    Called in a context that has no dispatching knot: a plain thread, or a
    fresh ``contextvars.Context`` standing in for a durable store's listener,
    which restores only the run id from the notice.
    """
    token = _current_run_id.set(run_id)
    try:
        with target:
            _Scripted(script=script, _config=KnotConfig(id="late"))
    finally:
        _current_run_id.reset(token)


async def _register_without_a_registrar(script: _Script, target: Tapestry, via: str) -> None:
    """After ``r`` has completed, register ``late`` with no registrar in scope."""
    await script.event("finished:r").wait()
    # Let the engine process r's completion before the registration lands.
    await asyncio.sleep(0.02)
    if via == "thread":
        worker = threading.Thread(
            target=_register_late_parentless, args=(script, target, script.run_id)
        )
        worker.start()
        await asyncio.to_thread(worker.join)
    else:
        contextvars.Context().run(_register_late_parentless, script, target, script.run_id)
    script.event("registered").set()


async def _run(t: Tapestry, **kwargs: Any) -> RunResult:
    # Generous: every scenario completes in well under a second when correct.
    return await asyncio.wait_for(t.run(RunRequest(parameters={"x": 1}), **kwargs), timeout=10.0)


# --------------------------------------------------- eager scheduling (M2)


async def test_child_starts_before_its_parents_slow_sibling_finishes() -> None:
    # Arrange: a and b are siblings; c depends only on b.  a cannot finish
    # until c has started, so a wave loop -- which starts c only after a --
    # deadlocks here.
    script = _Script()
    script.waits["a"] = "started:c"
    with Tapestry() as t:
        p = Parameter("x", int, _config=KnotConfig(id="p"))
        _Scripted(x=p, script=script, _config=KnotConfig(id="a"))
        b = _Scripted(x=p, script=script, _config=KnotConfig(id="b"))
        _Scripted(x=b, script=script, _config=KnotConfig(id="c"))

    # Act
    result = await _run(t)

    # Assert
    assert result.succeeded
    assert script.log.index("start:c") < script.log.index("finish:a")


async def test_knot_registered_mid_run_starts_before_an_unrelated_slow_knot_finishes() -> None:
    # Arrange: r registers `late` as its own child; `slow` cannot finish until
    # `late` has started.
    script = _Script()
    script.waits["slow"] = "started:late"
    with Tapestry() as t:
        p = Parameter("x", int, _config=KnotConfig(id="p"))
        _Scripted(x=p, script=script, _config=KnotConfig(id="slow"))
    with t:
        anchor = _Scripted(x=p, script=script, _config=KnotConfig(id="anchor"))
        _Registrar(
            x=anchor, script=script, target=t, late_parent=anchor, _config=KnotConfig(id="r")
        )

    # Act
    result = await _run(t, extensible=True)

    # Assert
    assert result.succeeded
    assert result.outputs["late"] == "late"
    assert script.log.index("start:late") < script.log.index("finish:slow")


# ------------------------------------------------------ lineage timing (M3b)


async def test_fast_knot_listed_after_a_slow_sibling_records_its_own_duration() -> None:
    # Arrange: b_fast sorts after a_slow, so the wave loop -- which stamped
    # finished_at while walking completions in list order -- charged it
    # a_slow's duration.
    slow_s = 0.4
    script = _Script()
    script.waits["a_slow"] = "finished:b_fast"
    script.delays["a_slow"] = slow_s
    with Tapestry() as t:
        p = Parameter("x", int, _config=KnotConfig(id="p"))
        _Scripted(x=p, script=script, _config=KnotConfig(id="a_slow"))
        _Scripted(x=p, script=script, _config=KnotConfig(id="b_fast"))

    # Act
    result = await _run(t)

    # Assert
    rows = {row.knot_id: row for row in result.lineage}
    fast = (rows["b_fast"].finished_at - rows["b_fast"].started_at).total_seconds()
    slow = (rows["a_slow"].finished_at - rows["a_slow"].started_at).total_seconds()
    assert slow >= slow_s
    assert fast < slow_s / 2


# ---------------------------------------- order independent of completion


def _mixed_outcome_graph(script: _Script) -> Tapestry:
    """p -> s0..s3; s2 fails; each s_i has a child c_i.

    c2 is skipped (its parent failed) and c3 fails synthetically
    (REQUIRE_ALL_PARENTS over s3 and the failed s2), so level 2 mixes knots
    the engine resolves without running and knots it dispatches.
    """
    script.failures.add("s2")
    with Tapestry() as t:
        p = Parameter("x", int, _config=KnotConfig(id="p"))
        s = [_Scripted(x=p, script=script, _config=KnotConfig(id=f"s{i}")) for i in range(4)]
        for i in range(4):
            script.waits[f"s{i}"] = f"go:s{i}"
        _Scripted(x=s[0], script=script, _config=KnotConfig(id="c0"))
        _Scripted(x=s[1], script=script, _config=KnotConfig(id="c1"))
        _Scripted(x=s[2], script=script, _config=KnotConfig(id="c2"))
        _Scripted(
            x=s[3],
            y=s[2],
            script=script,
            _config=KnotConfig(id="c3", error_policy=ErrorPolicy.REQUIRE_ALL_PARENTS),
        )
    return t


async def _release_in_order(script: _Script, order: tuple[str, ...]) -> None:
    for knot_id in order:
        await script.event(f"started:{knot_id}").wait()
    for knot_id in order:
        script.event(f"go:{knot_id}").set()
        await script.event(f"finished:{knot_id}").wait()


@pytest.mark.parametrize("finish_order", list(itertools.permutations(["s0", "s1", "s2", "s3"])))
async def test_reported_order_does_not_depend_on_completion_order(
    finish_order: tuple[str, ...],
) -> None:
    # Arrange
    script = _Script()
    t = _mixed_outcome_graph(script)
    releaser = asyncio.create_task(_release_in_order(script, finish_order))

    # Act
    result = await _run(t)
    await releaser

    # Assert: the siblings really did finish in the permuted order ...
    finishes = [entry for entry in script.log if entry.startswith("finish:s")]
    assert finishes == [f"finish:{k}" for k in finish_order]
    # ... yet every per-knot record comes out in the graph's order: by level,
    # knots resolved without running before dispatched ones, then topological.
    assert [row.knot_id for row in result.lineage] == [
        "p", "s0", "s1", "s2", "s3", "c2", "c3", "c0", "c1",
    ]  # fmt: skip
    assert [rec.knot_id for rec in result.exceptions] == ["s2", "c3"]
    assert result.skipped == ["c2"]
    assert list(result.outputs) == ["p", "s0", "s1", "s3", "c0", "c1"]


async def test_mid_run_knot_is_ordered_by_its_registrar_not_by_what_finished_first() -> None:
    # Arrange: r (level 1) registers `late` (a child of the root p), then
    # waits for d (level 3) to finish, so the engine absorbs `late` while
    # processing d's completion.  `late` still belongs one level past r --
    # where a wave loop would have run it -- not one past d.
    script = _Script()
    script.waits["d"] = "registered"
    with Tapestry() as t:
        p = Parameter("x", int, _config=KnotConfig(id="p"))
        a = _Scripted(x=p, script=script, _config=KnotConfig(id="a"))
        b = _Scripted(x=a, script=script, _config=KnotConfig(id="b"))
        _Scripted(x=b, script=script, _config=KnotConfig(id="d"))
    with t:
        _Registrar(
            x=p,
            script=script,
            target=t,
            late_parent=p,
            hold_until="finished:d",
            _config=KnotConfig(id="r"),
        )

    # Act
    result = await _run(t, extensible=True)

    # Assert
    assert result.succeeded
    assert [row.knot_id for row in result.lineage] == ["p", "a", "r", "b", "late", "d"]


@pytest.mark.parametrize("via", ["thread", "durable_delivery"])
@pytest.mark.parametrize("sibling_delay_s", [0.0, 0.01, 0.05, 0.15])
async def test_mid_run_knot_without_a_registrar_is_not_ordered_before_running_work(
    via: str, sibling_delay_s: float
) -> None:
    # Arrange: p -> a -> b -> r, plus s, a slow sibling of a.  Once r (level 3)
    # has completed, `late` is registered with no dispatching knot in scope --
    # from a plain thread, or the way a durable store delivers -- and is
    # absorbed when s (level 1) completes.  It must still be placed after
    # everything already dispatched, as the wave loop did, however long s
    # takes.
    script = _Script()
    script.waits["s"] = "registered"
    script.delays["s"] = sibling_delay_s
    with Tapestry() as t:
        p = Parameter("x", int, _config=KnotConfig(id="p"))
        a = _Scripted(x=p, script=script, _config=KnotConfig(id="a"))
        _Scripted(x=p, script=script, _config=KnotConfig(id="s"))
        b = _Scripted(x=a, script=script, _config=KnotConfig(id="b"))
        _Scripted(x=b, script=script, _config=KnotConfig(id="r"))
    registration = asyncio.create_task(_register_without_a_registrar(script, t, via))

    # Act
    result = await _run(t, extensible=True)
    await registration

    # Assert
    assert result.succeeded
    assert [row.knot_id for row in result.lineage] == ["p", "a", "s", "b", "r", "late"]


class _ThreadRegistrar(Knot):
    """Registers a parentless ``late`` with no registrar in scope, then finishes.

    ``via="thread"`` registers from a plain thread; any other value registers
    in a fresh context carrying only the run id, as a durable store delivers.
    """

    def __init__(self, *, script: _Script, target: Tapestry, via: str, **kwargs: Any) -> None:
        self._script = script
        self._target = target
        self._via = via
        super().__init__(**kwargs)

    async def process(self, **_inputs: Any) -> str:
        run_id = current_run_id()
        if self._via == "thread":
            worker = threading.Thread(
                target=_register_late_parentless, args=(self._script, self._target, run_id)
            )
            worker.start()
            await asyncio.to_thread(worker.join)
        else:
            contextvars.Context().run(_register_late_parentless, self._script, self._target, run_id)
        return self.knot_id


@pytest.mark.parametrize("via", ["thread", "durable_delivery"])
async def test_registrar_less_newcomer_order_does_not_depend_on_unrelated_progress(
    via: str,
) -> None:
    # Arrange: r (level 1) registers `late` with no registrar in scope while an
    # unrelated chain c0 -> ... -> c5 makes progress at a varying pace.  How far
    # the chain has got says nothing about where `late` belongs, so the record
    # order must be the same at every pace.
    orders: set[tuple[str, ...]] = set()
    for chain_delay_s in (0.0, 0.03, 0.1, 0.2):
        script = _Script()
        with Tapestry() as t:
            p = Parameter("x", int, _config=KnotConfig(id="p"))
            prev: Knot = p
            for i in range(6):
                script.delays[f"c{i}"] = chain_delay_s
                prev = _Scripted(x=prev, script=script, _config=KnotConfig(id=f"c{i}"))
        with t:
            _ThreadRegistrar(x=p, script=script, target=t, via=via, _config=KnotConfig(id="r"))

        # Act
        result = await _run(t, extensible=True)

        # Assert (per pace)
        assert result.succeeded
        assert result.outputs["late"] == "late"
        orders.add(tuple(row.knot_id for row in result.lineage))

    # Assert: one order across every pace -- registrar-less newcomers sort
    # after every knot with a known level, by registration sequence.
    assert orders == {("p", "c0", "r", "c1", "c2", "c3", "c4", "c5", "late")}


# ------------------------------------------------------- unbounded default


async def test_every_ready_sibling_is_in_flight_at_once_by_default() -> None:
    # Arrange: each sibling waits on a barrier that opens only when all of
    # them are waiting together, so the run completes only if nothing caps
    # how many knots are in flight.
    width = 200
    script = _Script()
    script.barrier = asyncio.Barrier(width)
    with Tapestry() as t:
        p = Parameter("x", int, _config=KnotConfig(id="p"))
        for i in range(width):
            _Scripted(x=p, script=script, _config=KnotConfig(id=f"k{i:03d}"))

    # Act
    result = await _run(t)

    # Assert
    assert result.succeeded
    assert len(result.outputs) == width + 1


# ----------------------------------------------------------- cancellation


async def test_cancelling_a_run_cancels_its_in_flight_knots_and_propagates() -> None:
    # Arrange
    script = _Script()
    script.waits["stuck"] = "never"
    with Tapestry() as t:
        p = Parameter("x", int, _config=KnotConfig(id="p"))
        _Scripted(x=p, script=script, _config=KnotConfig(id="stuck"))
    run = asyncio.create_task(t.run(RunRequest(parameters={"x": 1})))
    await asyncio.wait_for(script.event("started:stuck").wait(), timeout=10.0)

    # Act
    run.cancel()

    # Assert: the run itself raises.  The wave loop awaited the knot's task
    # directly, so a cancellation reached the knot, where ``Knot.__call__``
    # converts ``CancelledError`` into an ``Err`` (PIR-849), and the run
    # returned a failed RunResult instead.  ``Knot.__call__`` still swallows
    # it -- that is PIR-849's to fix -- but the engine no longer hides the
    # cancellation of the run.
    with pytest.raises(asyncio.CancelledError):
        await run
    assert "cancelled:stuck" in script.log
    assert "finish:stuck" not in script.log


async def test_in_flight_cleanup_has_finished_when_the_caller_sees_the_timeout() -> None:
    # Arrange: the stuck knot's cancellation handler awaits before it is done.
    script = _Script()
    script.waits["stuck"] = "never"
    script.cleanup_s = 0.05
    with Tapestry() as t:
        p = Parameter("x", int, _config=KnotConfig(id="p"))
        _Scripted(x=p, script=script, _config=KnotConfig(id="stuck"))

    # Act
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(t.run(RunRequest(parameters={"x": 1})), timeout=0.2)

    # Assert: no waiting here -- the engine awaited the cancelled knot before
    # letting the cancellation out of the run.
    assert "cleaned:stuck" in script.log
