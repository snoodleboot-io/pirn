"""Resumable batch tests (ADR agents-speaks-core, WS4b).

Resume-after-crash is now a ``RunHistory`` lineage query: an item's knot id
is ``item:<batch_id>:<key>``, so passing the same ``history=`` to a fresh
``MapAgent`` makes a re-run skip any item whose id already has an ``Ok``
lineage row. No checkpoint store is written or read.

Since PIR-874 the probe itself is a graph: one
:class:`~pirn_agents.batch.resumed_batch_item.ResumedBatchItem` per item in an
inner run that precedes the item graph, because its answer decides that graph's
shape. The behaviour below is unchanged by that; the probe's own lineage rows
are pinned on the engine path, which is where an inner run inherits the
enclosing run's history — ``_run_inner`` takes no history override, so a
standalone ``run()``'s probe rows go to whatever history was ambient when the
knot was constructed.
"""

from __future__ import annotations

from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.core.skipped import Skipped
from pirn.tapestry import Tapestry

from pirn_agents.batch.map_agent import MapAgent
from tests.batch.batch_doubles import StubAgent


async def _drain(runner: MapAgent, inputs: object) -> list:
    return [result async for result in runner.run(inputs)]  # type: ignore[arg-type]


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


async def test_each_resume_probe_is_its_own_knot() -> None:
    """PIR-874: the probe was a ``for`` loop awaiting history N times.

    However many items a batch resumed over, the run recorded one lineage row
    for the lot. Each probe is a knot now, so the run sees them — asserted on
    the engine path, where the inner run inherits the enclosing run's history.
    """
    history = InMemoryHistory()
    with Tapestry(history=history) as first:
        MapAgent(
            run_item=StubAgent(),
            items=["a", "b", "c"],
            _config=KnotConfig(id="map"),
            batch_id="b1",
            concurrency=4,
            history=history,
        )
        assert (await first.run(RunRequest())).succeeded
    # Even a first run probes: three items, three probe knots, nothing resumed.
    assert [
        len(await history.query_lineage_by_knot_id(f"probe_{index}")) for index in range(3)
    ] == [1, 1, 1]

    # The second run probes all three items before building its item graph.
    with Tapestry(history=history) as second:
        MapAgent(
            run_item=StubAgent(),
            items=["a", "b", "c"],
            _config=KnotConfig(id="map"),
            batch_id="b1",
            concurrency=4,
            history=history,
        )
        result = await second.run(RunRequest())
    assert result.succeeded, result.exceptions
    assert all(isinstance(item.outcome, Skipped) for item in result.outputs["map"])

    # Two runs, so two probe rows per item — one per run, each its own knot.
    probes = [await history.query_lineage_by_knot_id(f"probe_{index}") for index in range(3)]
    assert [len(rows) for rows in probes] == [2, 2, 2]
    assert all(row.outcome == "ok" for rows in probes for row in rows)


async def test_an_empty_batch_runs_no_probe() -> None:
    """No items, no probe run: ``Aggregator`` needs a parent."""
    history = InMemoryHistory()

    results = await _drain(
        MapAgent(
            run_item=StubAgent(),
            _config=KnotConfig(id="map-agent"),
            batch_id="b1",
            concurrency=4,
            history=history,
        ),
        [],
    )

    assert results == []
    assert await history.query_lineage_by_knot_id("probe_0") == []
