"""Resumable batch tests (ADR agents-speaks-core, WS4b).

Resume-after-crash is now a ``RunHistory`` lineage query: an item's knot id
is ``item:<batch_id>:<key>``, so passing the same ``history=`` to a fresh
``MapAgent`` makes a re-run skip any item whose id already has an ``Ok``
lineage row. No checkpoint store is written or read.
"""

from __future__ import annotations

from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.skipped import Skipped

from pirn_agents.batch.map_agent import MapAgent
from tests.batch.batch_doubles import StubAgent


async def _drain(runner: MapAgent, inputs: object) -> list:
    return [result async for result in runner.run(inputs)]


async def test_completed_items_get_an_ok_lineage_row() -> None:
    history = InMemoryHistory()
    runner = MapAgent(
        run_item=StubAgent(),
        _config=KnotConfig(id="map-agent"),
        batch_id="b1",
        concurrency=4,
        history=history,
    )

    await _drain(runner, ["a", "b", "c"])

    for key in ("0", "1", "2"):
        rows = await history.query_lineage_by_knot_id(f"item:b1:{key}")
        assert any(row.outcome == "ok" for row in rows), key


async def test_resume_skips_already_completed_items() -> None:
    history = InMemoryHistory()

    first = StubAgent()
    await _drain(
        MapAgent(
            run_item=first,
            _config=KnotConfig(id="map-agent"),
            batch_id="b1",
            concurrency=4,
            history=history,
        ),
        ["a", "b", "c"],
    )

    # Second run over the same inputs, same history: everything is already done.
    second = StubAgent()
    results = await _drain(
        MapAgent(
            run_item=second,
            _config=KnotConfig(id="map-agent"),
            batch_id="b1",
            concurrency=4,
            history=history,
        ),
        ["a", "b", "c"],
    )

    assert all(isinstance(r.outcome, Skipped) for r in results)
    assert second.calls == []  # the agent is never invoked for completed items


async def test_partial_resume_runs_only_remaining_items() -> None:
    history = InMemoryHistory()
    by_value = lambda item: str(item)  # noqa: E731 - key by the item's own value

    # Pre-seed: only "a" and "c" already done (a smaller first batch that
    # never mentions "b").
    seed = StubAgent()
    await _drain(
        MapAgent(
            run_item=seed,
            _config=KnotConfig(id="map-agent"),
            batch_id="b1",
            concurrency=4,
            key_fn=by_value,
            history=history,
        ),
        ["a", "c"],
    )

    agent = StubAgent()
    results = await _drain(
        MapAgent(
            run_item=agent,
            _config=KnotConfig(id="map-agent"),
            batch_id="b1",
            concurrency=4,
            key_fn=by_value,
            history=history,
        ),
        ["a", "b", "c"],
    )

    by_key = {r.key: r for r in results}
    assert isinstance(by_key["a"].outcome, Skipped)
    assert isinstance(by_key["c"].outcome, Skipped)
    assert by_key["b"].succeeded
    assert agent.calls == ["b"]  # only the one uncompleted item ran


async def test_failed_items_are_not_recorded_and_retry_on_resume() -> None:
    history = InMemoryHistory()

    # First pass: item "bad" (index 1) fails permanently, the others succeed.
    first = StubAgent(fail_items={"bad"})
    await _drain(
        MapAgent(
            run_item=first,
            _config=KnotConfig(id="map-agent"),
            batch_id="b1",
            concurrency=4,
            history=history,
        ),
        ["a", "bad", "c"],
    )

    rows = await history.query_lineage_by_knot_id("item:b1:1")
    assert not any(row.outcome == "ok" for row in rows)  # failed item not recorded as ok

    # Resume: the previously-failed item re-runs (now succeeds); others skip.
    second = StubAgent()
    results = await _drain(
        MapAgent(
            run_item=second,
            _config=KnotConfig(id="map-agent"),
            batch_id="b1",
            concurrency=4,
            history=history,
        ),
        ["a", "bad", "c"],
    )
    by_key = {r.key: r for r in results}
    assert by_key["1"].succeeded
    assert second.calls == ["bad"]


async def test_no_history_means_no_resume() -> None:
    """The default: without a ``history=``, every item runs every time."""
    agent = StubAgent()
    runner = MapAgent(
        run_item=agent, _config=KnotConfig(id="map-agent"), batch_id="b1", concurrency=4
    )

    await _drain(runner, ["a", "b"])
    await _drain(runner, ["a", "b"])

    assert agent.calls == ["a", "b", "a", "b"]


async def test_checkpoint_scope_isolates_resume_state() -> None:
    """``run``'s ``checkpoint_scope=`` (mirroring the pre-migration suffix)
    namespaces the item knot id, so two scopes never share a skip-set."""
    history = InMemoryHistory()
    seeded = [
        result
        async for result in MapAgent(
            run_item=StubAgent(),
            _config=KnotConfig(id="map-agent"),
            batch_id="b1",
            concurrency=4,
            history=history,
        ).run(["x"], checkpoint_scope="scope-a")
    ]
    assert seeded[0].succeeded

    # A different scope has never seen "x" and runs it.
    second_agent = StubAgent()
    results = [
        result
        async for result in MapAgent(
            run_item=second_agent,
            _config=KnotConfig(id="map-agent"),
            batch_id="b1",
            concurrency=4,
            history=history,
        ).run(["x"], checkpoint_scope="scope-b")
    ]
    assert second_agent.calls == ["x"]
    assert results[0].succeeded
