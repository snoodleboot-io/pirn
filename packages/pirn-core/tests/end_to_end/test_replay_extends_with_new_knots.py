"""``ReplaySession(allow_new_knots=True)`` — replay a prefix, run the rest live.

ADR "agents speaks core" WS3 core seam. The default posture (unchanged, and
covered by ``test_replay_execution.py``) is strict: every non-``Parameter``
knot must have a matching recorded row or the engine raises
``ReplayMismatchError`` — a recording that cannot be honoured never silently
falls back to live execution. ``allow_new_knots=True`` is an explicit,
additive opt-in for the one case that needs a different answer: continuing a
run whose original terminals stopped short of a knot the caller now wants to
run for the first time (e.g. a HITL run suspended at an approval gate, then
resumed past it).
"""

from __future__ import annotations

from typing import Any, ClassVar

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.recording.replay_mismatch_error import ReplayMismatchError
from pirn.recording.replay_session import ReplaySession
from pirn.tapestry import Tapestry


class Doubler(Knot):
    """Doubles its input and logs every actual invocation."""

    invocations: ClassVar[list[int]] = []

    def __init__(self, x: Knot, **kwargs: Any) -> None:
        super().__init__(x=x, **kwargs)

    async def process(self, x: int, **_: Any) -> int:
        Doubler.invocations.append(x)
        return x * 2


class Incrementer(Knot):
    """Adds one to its input and logs every actual invocation."""

    invocations: ClassVar[list[int]] = []

    def __init__(self, x: Knot, **kwargs: Any) -> None:
        super().__init__(x=x, **kwargs)

    async def process(self, x: int, **_: Any) -> int:
        Incrementer.invocations.append(x)
        return x + 1


@pytest.fixture(autouse=True)
def _clear_invocations() -> None:
    Doubler.invocations.clear()
    Incrementer.invocations.clear()


async def test_default_posture_still_raises_for_an_unrecorded_knot() -> None:
    """The existing, documented invariant: no silent fallback by default."""
    with Tapestry() as tapestry:
        param = Parameter(name="x", type_=int)
        Doubler(x=param, _config=KnotConfig(id="double"))
    original = await tapestry.run(RunRequest(parameters={"x": 5}))

    with Tapestry(history=tapestry.history, data_store=tapestry.data_store) as extended:
        param = Parameter(name="x", type_=int)
        doubled = Doubler(x=param, _config=KnotConfig(id="double"))
        Incrementer(x=doubled, _config=KnotConfig(id="increment"))

    session = await ReplaySession.from_history(history=tapestry.history, run_id=original.run_id)
    assert session.allow_new_knots is False
    with pytest.raises(ReplayMismatchError):
        await extended.run(RunRequest(parameters={"x": 5}), replay=session)


async def test_allow_new_knots_serves_the_prefix_and_runs_the_rest_live() -> None:
    with Tapestry() as tapestry:
        param = Parameter(name="x", type_=int)
        Doubler(x=param, _config=KnotConfig(id="double"))
    original = await tapestry.run(RunRequest(parameters={"x": 5}))
    assert Doubler.invocations == [5]
    assert original.outputs["double"] == 10

    # A second, wider graph over the same history/data_store: same "double"
    # knot id and config, plus a genuinely new "increment" knot downstream —
    # the shape of resuming a suspended run past the point it stopped at.
    with Tapestry(history=tapestry.history, data_store=tapestry.data_store) as extended:
        param = Parameter(name="x", type_=int)
        doubled = Doubler(x=param, _config=KnotConfig(id="double"))
        Incrementer(x=doubled, _config=KnotConfig(id="increment"))

    session = await ReplaySession.from_history(
        history=tapestry.history, run_id=original.run_id, allow_new_knots=True
    )
    assert session.allow_new_knots is True

    continued = await extended.run(RunRequest(parameters={"x": 5}), replay=session)

    assert continued.succeeded
    # "double" was served from the recording — not invoked a second time.
    assert Doubler.invocations == [5]
    assert continued.outputs["double"] == 10
    # "increment" has no recorded row at all, so it ran live for real.
    assert Incrementer.invocations == [10]
    assert continued.outputs["increment"] == 11


async def test_allow_new_knots_still_raises_for_a_covered_knot_with_mismatched_inputs() -> None:
    """Only *uncovered* knots get the pass — a recorded, covered one still raises."""
    with Tapestry() as tapestry:
        param = Parameter(name="x", type_=int)
        Doubler(x=param, _config=KnotConfig(id="double"))
    original = await tapestry.run(RunRequest(parameters={"x": 5}))

    with Tapestry(history=tapestry.history, data_store=tapestry.data_store) as extended:
        param = Parameter(name="x", type_=int)
        doubled = Doubler(x=param, _config=KnotConfig(id="double"))
        Incrementer(x=doubled, _config=KnotConfig(id="increment"))

    session = await ReplaySession.from_history(
        history=tapestry.history, run_id=original.run_id, allow_new_knots=True
    )
    # "double" has a recorded row (it is covered), so allow_new_knots does not
    # apply to it; a different x here changes its parent_input_hashes and the
    # strict match still raises, even though "increment" would have been
    # allowed to run live as a genuinely new knot.
    with pytest.raises(ReplayMismatchError):
        await extended.run(RunRequest(parameters={"x": 99}), replay=session)
