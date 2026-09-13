"""The nested-run depth and cycle guard through real nested runs (WS0).

``Tapestry(max_nesting_depth=n)`` caps how many runs may nest below a run of
that tapestry; the cap is inherited by inner tapestries through the run
context and only ever tightened.  A run that would exceed it, or a container
class re-entering itself, fails inside the container knot as an ``Err`` whose
record names the guard error.  Without a cap anywhere on the path, nesting is
unbounded and every existing pipeline behaves exactly as before.
"""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_nesting import RunNesting
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.nodes.loop_sub_tapestry import LoopSubTapestry
from pirn.nodes.source import Source
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

pytestmark = pytest.mark.timeout(60)


class _Depth(Source):
    """Reports the nesting depth of the run that dispatched it."""

    async def process(self, **_: Any) -> int:
        return RunNesting.current().depth


class _Descend(SubTapestry):
    """Nests itself ``remaining`` more times, then reports the depth reached."""

    async def process(self, remaining: int, **_: Any) -> Knot:
        if remaining == 0:
            return _Depth(_config=KnotConfig(id="depth"))
        return _Descend(remaining=remaining - 1, _config=KnotConfig(id=f"d{remaining - 1}"))


class _Level(SubTapestry):
    """One link of a chain of *distinct* container classes (see ``_LEVELS``).

    Each link nests the next class down, so the chain exercises the depth
    cap alone: no class ever re-enters itself, which the cycle guard would
    refuse first.
    """

    async def process(self, remaining: int, **_: Any) -> Knot:
        if remaining == 0:
            return _Depth(_config=KnotConfig(id="depth"))
        return _LEVELS[remaining - 1](
            remaining=remaining - 1, _config=KnotConfig(id=f"l{remaining - 1}")
        )


_LEVELS: list[type[_Level]] = [type(f"_Level{i}", (_Level,), {}) for i in range(8)]


class _Capped(SubTapestry):
    """Runs its inner pipeline under an inner tapestry with its own cap."""

    async def process(self, remaining: int, cap: int, **_: Any) -> Knot:
        return _Descend(remaining=remaining, _config=KnotConfig(id="inner"))

    async def _run_inner(self, tapestry: Tapestry, **kwargs: Any) -> RunResult:  # type: ignore[override]
        tapestry._max_nesting_depth = self.config_values["cap"]
        return await super()._run_inner(tapestry, **kwargs)


class _Other(SubTapestry):
    async def process(self, **_: Any) -> Knot:
        return _Depth(_config=KnotConfig(id="depth"))


class _ViaOther(SubTapestry):
    """Re-enters itself — same class, same knot id — through another container."""

    async def process(self, again: bool, **_: Any) -> Knot:
        if not again:
            return _Other(_config=KnotConfig(id="other"))
        return _ViaOther(again=False, _config=KnotConfig(id="top"))


class _ViaOtherSibling(SubTapestry):
    """Nests another instance of its own class under a *different* knot id."""

    async def process(self, again: bool, **_: Any) -> Knot:
        if not again:
            return _Other(_config=KnotConfig(id="other"))
        return _ViaOtherSibling(again=False, _config=KnotConfig(id="sibling"))


class _InnerLoop(LoopSubTapestry[int]):
    def step(self, state: int) -> tuple[Tapestry, int] | None:
        if state >= 2:
            return None
        with Tapestry() as t:
            _Depth(_config=KnotConfig(id="depth"))
        return t, state + 1

    def fold(self, state: int, result: RunResult) -> int:
        return state


class _OuterLoop(LoopSubTapestry[int]):
    """Each iteration runs another loop: nested loops are not a cycle."""

    def step(self, state: int) -> tuple[Tapestry, int] | None:
        if state >= 2:
            return None
        with Tapestry() as t:
            seed = Parameter("s", int, default=0, _config=KnotConfig(id="seed"))
            _InnerLoop(state=seed, _config=KnotConfig(id="inner"))
        return t, state + 1

    def fold(self, state: int, result: RunResult) -> int:
        return state


def _innermost_error_types(result: RunResult) -> list[str]:
    return [rec.exc_type for rec in result.exceptions]


async def _child_error_types(tapestry: Tapestry, run_id: str) -> list[str]:
    """Walk history down from *run_id* and return the deepest run's exception types."""
    children = await tapestry.history.children_of(run_id)
    if not children:
        run = await tapestry.history.get_run(run_id)
        assert run is not None
        return _innermost_error_types(run)
    return await _child_error_types(tapestry, children[0].run_id)


async def test_unguarded_nesting_is_unbounded() -> None:
    # Arrange
    with Tapestry() as t:
        _Descend(remaining=6, _config=KnotConfig(id="top"))

    # Act
    result = await t.run(RunRequest())

    # Assert
    assert result.succeeded
    assert result.outputs["top"] == 7


async def test_a_knot_can_read_its_depth() -> None:
    with Tapestry() as t:
        _Depth(_config=KnotConfig(id="root_depth"))
        _Descend(remaining=1, _config=KnotConfig(id="top"))
    result = await t.run(RunRequest())
    assert result.outputs["root_depth"] == 0
    assert result.outputs["top"] == 2


async def test_nested_run_path_lists_the_enclosing_runs() -> None:
    # Arrange
    with Tapestry() as t:
        _Descend(remaining=1, _config=KnotConfig(id="top"))

    # Act
    result = await t.run(RunRequest(run_id="r0"))

    # Assert
    assert result.run_path == "/r0"
    (child,) = await t.history.children_of("r0")
    assert child.run_path == f"/r0/{child.run_id}"
    (grandchild,) = await t.history.children_of(child.run_id)
    assert grandchild.run_path == f"/r0/{child.run_id}/{grandchild.run_id}"


async def test_nesting_at_the_cap_succeeds() -> None:
    with Tapestry(max_nesting_depth=3) as t:
        _LEVELS[2](remaining=2, _config=KnotConfig(id="top"))
    result = await t.run(RunRequest())
    assert result.succeeded
    assert result.outputs["top"] == 3


async def test_nesting_over_the_cap_fails_the_container_that_went_too_deep() -> None:
    # Arrange
    with Tapestry(max_nesting_depth=2) as t:
        _LEVELS[4](remaining=4, _config=KnotConfig(id="top"))

    # Act
    result = await t.run(RunRequest(run_id="r0"))

    # Assert: the outer run fails through the chain of containers, and the
    # deepest recorded run holds the guard error against the knot that tried
    # to start one run too many.
    assert not result.succeeded
    assert _innermost_error_types(result) == ["SubTapestryError"]
    assert await _child_error_types(t, "r0") == ["NestingDepthExceededError"]


async def test_the_cap_is_inherited_by_inner_tapestries() -> None:
    # Arrange: only the outermost tapestry sets a cap; the inner ones are
    # built with defaults inside process().
    with Tapestry(max_nesting_depth=1) as t:
        _Descend(remaining=2, _config=KnotConfig(id="top"))

    # Act
    result = await t.run(RunRequest(run_id="r0"))

    # Assert
    assert not result.succeeded
    assert await _child_error_types(t, "r0") == ["NestingDepthExceededError"]


async def test_an_inner_tapestry_can_only_tighten_the_cap() -> None:
    # Arrange: the outer tapestry has no cap; the inner run sets one of 2,
    # which the runs below it inherit.
    with Tapestry() as t:
        _Capped(remaining=3, cap=2, _config=KnotConfig(id="top"))

    # Act
    result = await t.run(RunRequest(run_id="r0"))

    # Assert
    assert not result.succeeded
    assert await _child_error_types(t, "r0") == ["NestingDepthExceededError"]


async def test_a_container_re_entering_itself_is_a_cycle_when_guarded() -> None:
    # Arrange: _ViaOther("top") -> _ViaOther("top") is refused at depth 2,
    # well under the cap.
    with Tapestry(max_nesting_depth=10) as t:
        _ViaOther(again=True, _config=KnotConfig(id="top"))

    # Act
    result = await t.run(RunRequest(run_id="r0"))

    # Assert
    assert not result.succeeded
    assert await _child_error_types(t, "r0") == ["NestedRunCycleError"]


async def test_another_instance_of_the_same_class_is_not_a_cycle() -> None:
    # Arrange: the nesting key carries the knot id (ADR WS1), so a container
    # nesting a *different* instance of its own class — an agent handing a
    # task to another agent of the same class — is allowed under a cap.
    with Tapestry(max_nesting_depth=10) as t:
        _ViaOtherSibling(again=True, _config=KnotConfig(id="top"))

    # Act
    result = await t.run(RunRequest(run_id="r0"))

    # Assert
    assert result.succeeded, result.exceptions
    assert result.outputs["top"] == 3


async def test_re_entry_is_allowed_without_a_cap() -> None:
    with Tapestry() as t:
        _ViaOther(again=True, _config=KnotConfig(id="top"))
    result = await t.run(RunRequest())
    assert result.succeeded
    assert result.outputs["top"] == 3


async def test_nested_loops_are_not_a_cycle() -> None:
    # Arrange: each outer iteration runs an inner loop; iteration runs add
    # depth but no key, so the guard sees Outer -> Inner, never Inner -> Inner.
    with Tapestry(max_nesting_depth=8) as t:
        seed = Parameter("s", int, default=0, _config=KnotConfig(id="seed"))
        _OuterLoop(state=seed, _config=KnotConfig(id="outer"))

    # Act
    result = await t.run(RunRequest())

    # Assert
    assert result.succeeded
    assert result.outputs["outer"] == 2


async def test_loop_iterations_count_toward_depth() -> None:
    # Arrange: outer run (0) -> loop run (1) -> iteration (2) -> inner loop
    # run (3) -> inner iteration (4): a cap of 3 refuses the inner iteration.
    with Tapestry(max_nesting_depth=3) as t:
        seed = Parameter("s", int, default=0, _config=KnotConfig(id="seed"))
        _OuterLoop(state=seed, _config=KnotConfig(id="outer"))

    # Act
    result = await t.run(RunRequest())

    # Assert
    assert not result.succeeded


def test_max_nesting_depth_is_validated() -> None:
    with pytest.raises(ValueError, match="max_nesting_depth"):
        Tapestry(max_nesting_depth=-1)
    with pytest.raises(ValueError, match="max_nesting_depth"):
        Tapestry(max_nesting_depth=True)  # type: ignore[arg-type]
    assert Tapestry(max_nesting_depth=4).max_nesting_depth == 4
    assert Tapestry().max_nesting_depth is None
