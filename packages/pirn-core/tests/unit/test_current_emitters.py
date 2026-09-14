"""Tests for the public ``Tapestry.current_emitters()`` / ``Tapestry.current_emitter_error_policy()``
accessors, and for ``EmitterFanout.emit_status`` — the sanctioned way to deliver
an ad hoc ``StatusEvent`` to a run's emitters from inside a knot's ``process()``.

Mirrors ``test_current_run_id.py``: emitters have always been carried in a
``ContextVar``, but only as the private ``_current_emitters``. A downstream
domain publishing its own sub-knot events (an LLM call, a tool call, a
retrieval step) needs the same run-scoped emitter subscription the engine
itself fans lifecycle transitions to, without reaching into a private name.
"""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.emitters.emitter import Emitter
from pirn.emitters.emitter_error_policy import EmitterErrorPolicy
from pirn.engine.emitter_fanout import EmitterFanout
from pirn.managers.knot_state import KnotState
from pirn.managers.status_event import StatusEvent
from pirn.tapestry import Tapestry


class _CapturingEmitter(Emitter):
    def __init__(self) -> None:
        self.statuses: list[StatusEvent] = []

    async def on_status(self, event: StatusEvent) -> None:
        self.statuses.append(event)


class _BrokenEmitter(Emitter):
    async def on_status(self, event: StatusEvent) -> None:
        raise RuntimeError("broken emitter")


class CurrentEmittersTests(unittest.IsolatedAsyncioTestCase):
    def test_returns_empty_list_outside_a_run(self) -> None:
        assert Tapestry.current_emitters() == []

    def test_returns_warn_policy_outside_a_run(self) -> None:
        assert Tapestry.current_emitter_error_policy() is EmitterErrorPolicy.WARN

    async def test_returns_the_runs_emitters_during_a_run(self) -> None:
        seen: list[list[Emitter]] = []
        emitter = _CapturingEmitter()

        @knot
        async def _capture(x: int) -> int:
            seen.append(Tapestry.current_emitters())
            return x

        with Tapestry(emitters=[emitter]) as t:
            p = Parameter("x", int)
            a = _capture(x=p, _config=KnotConfig(id="a"))

        result = await t.run(RunRequest(parameters={"x": 1}), terminals=a)

        assert result.succeeded
        assert seen == [[emitter]]

    async def test_resets_after_the_run(self) -> None:
        with Tapestry(emitters=[_CapturingEmitter()]) as t:
            p = Parameter("x", int)

            @knot
            async def _noop(x: int) -> int:
                return x

            a = _noop(x=p, _config=KnotConfig(id="a"))

        await t.run(RunRequest(parameters={"x": 1}), terminals=a)

        assert Tapestry.current_emitters() == []


class EmitStatusTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _event() -> StatusEvent:
        return StatusEvent(
            run_id="r1",
            knot_id="k1",
            state=KnotState.SUCCEEDED,
            extra={"kind": "llm", "model": "m"},
        )

    async def test_delivers_to_explicit_emitters(self) -> None:
        emitter = _CapturingEmitter()
        event = self._event()
        await EmitterFanout.emit_status(event, emitters=[emitter])
        assert emitter.statuses == [event]

    async def test_delivers_to_current_emitters_when_none_given(self) -> None:
        emitter = _CapturingEmitter()
        event = self._event()

        @knot
        async def _emit(x: int) -> int:
            await EmitterFanout.emit_status(event)
            return x

        with Tapestry(emitters=[emitter]) as t:
            p = Parameter("x", int)
            a = _emit(x=p, _config=KnotConfig(id="a"))

        result = await t.run(RunRequest(parameters={"x": 1}), terminals=a)

        assert result.succeeded
        # The engine's own lifecycle transitions land here too; only assert
        # that our ad hoc event was among them.
        assert event in emitter.statuses

    async def test_no_op_with_no_emitters(self) -> None:
        # Must not raise even with nothing subscribed.
        await EmitterFanout.emit_status(self._event(), emitters=[])

    async def test_ignore_policy_swallows_emitter_error(self) -> None:
        await EmitterFanout.emit_status(
            self._event(), emitters=[_BrokenEmitter()], policy=EmitterErrorPolicy.IGNORE
        )

    async def test_warn_policy_logs_and_continues(self) -> None:
        emitter = _CapturingEmitter()
        event = self._event()
        await EmitterFanout.emit_status(
            event,
            emitters=[_BrokenEmitter(), emitter],
            policy=EmitterErrorPolicy.WARN,
        )
        # The broken emitter's failure must not stop the good one from
        # receiving the event.
        assert emitter.statuses == [event]

    async def test_raise_policy_propagates(self) -> None:
        with self.assertRaises(RuntimeError):
            await EmitterFanout.emit_status(
                self._event(),
                emitters=[_BrokenEmitter()],
                policy=EmitterErrorPolicy.RAISE,
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
