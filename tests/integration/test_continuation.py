"""Tests for continues() and WithContinuation."""

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.nodes.continuation import END, Next, continues
from pirn.tapestry import Tapestry


@knot
async def fetch(query: str, **_) -> dict:
    return {"found": True, "content": f"results for {query}"}


@knot
async def summarise(text: str, **_) -> str:
    return f"summary: {text[:40]}"


@knot
async def flag_missing(**_) -> str:
    return "nothing found"


POOL = {"summarise": summarise, "flag_missing": flag_missing}


async def test_continues_spawns_successor():
    with Tapestry() as t:
        q = Parameter("query", str, _config=KnotConfig(id="q"))
        f = fetch(query=q, _config=KnotConfig(id="fetch"))
        continues(f, fn=lambda r: [Next("summarise", {"text": r["content"]})], pool=POOL)

    r = await t.run(RunRequest(parameters={"query": "test"}), extensible=True)
    assert r.succeeded, [(e.knot_id, e.message) for e in r.exceptions]
    assert "fetch" in r.outputs
    assert "fetch__cont" in r.outputs
    spawned = [k for k in r.outputs if "summarise" in k]
    assert spawned
    assert r.outputs[spawned[0]].startswith("summary:")


async def test_end_terminates_explicitly():
    with Tapestry() as t:
        q = Parameter("query", str, _config=KnotConfig(id="q2"))
        f = fetch(query=q, _config=KnotConfig(id="fetch2"))
        continues(f, fn=lambda _: [Next(END)], pool={})

    r = await t.run(RunRequest(parameters={"query": "x"}), extensible=True)
    assert r.succeeded, [(e.knot_id, e.message) for e in r.exceptions]
    end_knots = [k for k in r.outputs if "end" in k]
    assert end_knots


async def test_continuation_branches():
    """Continuation can return multiple successors — both run."""
    with Tapestry() as t:
        q = Parameter("query", str, _config=KnotConfig(id="q3"))
        f = fetch(query=q, _config=KnotConfig(id="fetch3"))
        continues(
            f,
            fn=lambda r: [
                Next("summarise", {"text": r["content"]}, id="sum_a"),
                Next("summarise", {"text": r["content"] + "!"}, id="sum_b"),
            ],
            pool=POOL,
        )

    r = await t.run(RunRequest(parameters={"query": "multi"}), extensible=True)
    assert r.succeeded, [(e.knot_id, e.message) for e in r.exceptions]
    assert "sum_a" in r.outputs
    assert "sum_b" in r.outputs


async def test_missing_pool_action_raises():
    with Tapestry() as t:
        q = Parameter("query", str, _config=KnotConfig(id="q4"))
        f = fetch(query=q, _config=KnotConfig(id="fetch4"))
        continues(f, fn=lambda _: [Next("unknown_action")], pool={})

    r = await t.run(RunRequest(parameters={"query": "x"}), extensible=True)
    assert not r.succeeded
    assert any("not found in pool" in e.message for e in r.exceptions)
