"""End-to-end cross-run lineage tests.

Demonstrates the central Phase 2 promise: lineage records reference values
by content hash; runs that produce or consume the same value are joinable
across run boundaries with no extra plumbing.
"""

from __future__ import annotations

from pirn import KnotConfig, Parameter, RunRequest, Tapestry, knot


@knot
async def square(x: int) -> int:
    return x * x


@knot
async def plus_one(x: int) -> int:
    return x + 1


async def test_same_input_produces_same_hash():
    with Tapestry() as t:
        p = Parameter("x", int)
        square(x=p, _config=KnotConfig(id="sq"))

    r1 = await t.run(RunRequest(parameters={"x": 5}))
    r2 = await t.run(RunRequest(parameters={"x": 5}))

    h1 = next(rec.output_hash for rec in r1.lineage if rec.knot_id == "sq")
    h2 = next(rec.output_hash for rec in r2.lineage if rec.knot_id == "sq")
    assert h1 == h2


async def test_cross_run_query_by_output_hash():
    with Tapestry() as t:
        p = Parameter("x", int)
        square(x=p, _config=KnotConfig(id="sq"))

    # Three runs with the same input — all produce the same square output hash.
    for _ in range(3):
        await t.run(RunRequest(parameters={"x": 5}))
    # One run with a different input.
    await t.run(RunRequest(parameters={"x": 6}))

    last = await t.run(RunRequest(parameters={"x": 5}))
    target_hash = next(
        rec.output_hash for rec in last.lineage if rec.knot_id == "sq"
    )
    matches = await t.history.query_lineage_by_output_hash(target_hash)
    # Five total runs of x=5 (3 + 1 last), all match.
    assert len([m for m in matches if m.knot_id == "sq"]) == 4


async def test_cross_run_query_finds_consumers_by_input_hash():
    """A value produced in run A and consumed in run B (with same input)
    is joinable via input-hash query."""
    with Tapestry() as t:
        p = Parameter("x", int)
        sq = square(x=p, _config=KnotConfig(id="sq"))
        plus_one(x=sq, _config=KnotConfig(id="po"))

    r1 = await t.run(RunRequest(parameters={"x": 4}))
    r2 = await t.run(RunRequest(parameters={"x": 4}))

    # The plus_one knot in both runs consumed the same input hash
    # (because square produced the same output for x=4).
    sq_hash_r1 = next(rec.output_hash for rec in r1.lineage if rec.knot_id == "sq")
    sq_hash_r2 = next(rec.output_hash for rec in r2.lineage if rec.knot_id == "sq")
    assert sq_hash_r1 == sq_hash_r2

    # query: who consumed this value as input?
    consumers = await t.history.query_lineage_by_input_hash(sq_hash_r1)
    consumer_ids = {c.knot_id for c in consumers}
    assert "po" in consumer_ids
    # Both runs produced a `po` lineage with this input hash → 2 records.
    po_records = [c for c in consumers if c.knot_id == "po"]
    assert len(po_records) == 2


async def test_query_by_knot_id_across_runs():
    with Tapestry() as t:
        p = Parameter("x", int)
        square(x=p, _config=KnotConfig(id="sq"))

    for value in [1, 2, 3, 4, 5]:
        await t.run(RunRequest(parameters={"x": value}))

    matches = await t.history.query_lineage_by_knot_id("sq")
    assert len(matches) == 5


async def test_complete_run_persisted_in_history():
    with Tapestry() as t:
        p = Parameter("x", int, default=1)
        square(x=p, _config=KnotConfig(id="sq"))

    result = await t.run(RunRequest(run_id="my-special-run"))
    fetched = await t.history.get_run("my-special-run")
    assert fetched is not None
    assert fetched.run_id == "my-special-run"
    assert fetched.outputs == result.outputs


async def test_data_store_holds_values_by_hash():
    with Tapestry() as t:
        p = Parameter("x", int, default=4)
        square(x=p, _config=KnotConfig(id="sq"))

    result = await t.run(RunRequest())
    sq_hash = next(rec.output_hash for rec in result.lineage if rec.knot_id == "sq")

    # The data store should hold the value 16 at this hash.
    assert await t.data_store.has(sq_hash)
    value = await t.data_store.get(sq_hash)
    assert value == 16


async def test_scrub_data_preserves_lineage():
    """Scrubbing a value from data store doesn't affect lineage."""
    with Tapestry() as t:
        p = Parameter("x", int, default=4)
        square(x=p, _config=KnotConfig(id="sq"))

    result = await t.run(RunRequest())
    sq_hash = next(rec.output_hash for rec in result.lineage if rec.knot_id == "sq")

    await t.data_store.scrub(sq_hash)
    assert not await t.data_store.has(sq_hash)

    # Lineage record still exists.
    matches = await t.history.query_lineage_by_output_hash(sq_hash)
    assert len(matches) == 1
