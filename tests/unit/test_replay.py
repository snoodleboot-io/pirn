"""Tests for pirn.replay — replay_run and compare_runs."""

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.replay import KnotDiff, compare_runs, replay_run
from pirn.tapestry import Tapestry
from pirn.backends.sqlite.sqlite_history import SQLiteHistory


@knot
async def double(x: int) -> int:
    return x * 2


@knot
async def add(a: int, b: int) -> int:
    return a + b


def build_tapestry(history=None):
    with Tapestry(history=history) as t:
        x = Parameter("x", int, _config=KnotConfig(id="x"))
        b = Parameter("b", int, _config=KnotConfig(id="b"))
        d = double(x=x, _config=KnotConfig(id="double"))
        add(a=d, b=b, _config=KnotConfig(id="add"))
    return t


@pytest.mark.asyncio
async def test_replay_run_produces_same_result():
    history = SQLiteHistory()
    t = build_tapestry(history=history)

    params = {"x": 5, "b": 3}
    original = await t.run(RunRequest(parameters=params))

    replayed = await replay_run(
        history=history,
        run_id=original.run_id,
        tapestry=t,
        base_parameters=params,
    )

    assert replayed.succeeded
    assert replayed.outputs["add"] == original.outputs["add"]


@pytest.mark.asyncio
async def test_replay_run_with_override_changes_output():
    history = SQLiteHistory()
    t = build_tapestry(history=history)

    params = {"x": 5, "b": 3}
    original = await t.run(RunRequest(parameters=params))

    replayed = await replay_run(
        history=history,
        run_id=original.run_id,
        tapestry=t,
        base_parameters=params,
        parameter_overrides={"x": 10},
    )

    assert replayed.outputs["double"] == 20  # 10 * 2
    assert replayed.outputs["add"] == 23  # 20 + 3


@pytest.mark.asyncio
async def test_replay_run_raises_for_unknown_run_id():
    history = SQLiteHistory()
    t = build_tapestry(history=history)

    with pytest.raises(KeyError, match="not found"):
        await replay_run(
            history=history,
            run_id="run-nonexistent",
            tapestry=t,
            base_parameters={"x": 1, "b": 1},
        )


@pytest.mark.asyncio
async def test_replay_run_accepts_custom_run_id():
    history = SQLiteHistory()
    t = build_tapestry(history=history)

    params = {"x": 2, "b": 1}
    original = await t.run(RunRequest(parameters=params))

    replayed = await replay_run(
        history=history,
        run_id=original.run_id,
        tapestry=t,
        base_parameters=params,
        new_run_id="run-custom-id",
    )

    assert replayed.run_id == "run-custom-id"


# ----------------------------------------------------------------- compare_runs


@pytest.mark.asyncio
async def test_compare_runs_identical_shows_no_changes():
    history = SQLiteHistory()
    t = build_tapestry(history=history)

    params = {"x": 3, "b": 7}
    r1 = await t.run(RunRequest(parameters=params))
    r2 = await t.run(RunRequest(parameters=params))

    diffs = compare_runs(r1, r2)
    assert all(not d.changed for d in diffs)


@pytest.mark.asyncio
async def test_compare_runs_detects_changed_output():
    history = SQLiteHistory()
    t = build_tapestry(history=history)

    r1 = await t.run(RunRequest(parameters={"x": 3, "b": 1}))
    r2 = await t.run(RunRequest(parameters={"x": 5, "b": 1}))

    diffs = compare_runs(r1, r2)
    by_id = {d.knot_id: d for d in diffs}

    assert by_id["double"].changed
    assert by_id["double"].output_changed
    assert by_id["add"].changed


@pytest.mark.asyncio
async def test_compare_runs_unchanged_knot_not_flagged():
    history = SQLiteHistory()
    t = build_tapestry(history=history)

    # Only b changes — double is unaffected
    r1 = await t.run(RunRequest(parameters={"x": 4, "b": 1}))
    r2 = await t.run(RunRequest(parameters={"x": 4, "b": 9}))

    diffs = compare_runs(r1, r2)
    by_id = {d.knot_id: d for d in diffs}

    assert not by_id["double"].changed
    assert by_id["add"].changed


def test_knot_diff_str_unchanged():
    d = KnotDiff("my_knot", "ok", "ok", "abc", "abc")
    assert str(d) == "= my_knot"


def test_knot_diff_str_hash_changed():
    d = KnotDiff("my_knot", "ok", "ok", "abc", "xyz")
    assert "~" in str(d)
    assert "hash changed" in str(d)


def test_knot_diff_str_outcome_changed():
    d = KnotDiff("my_knot", "ok", "err", "abc", "abc")
    assert "ok → err" in str(d)
