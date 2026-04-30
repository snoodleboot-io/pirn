"""Branch / BranchOutput tests."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.nodes.branch.branch import Branch
from pirn.tapestry import Tapestry


@knot
async def handle_tool(p: dict) -> str:
    return f"tool:{p['name']}"


@knot
async def handle_resp(p: dict) -> str:
    return f"resp:{p['text']}"


async def test_branch_selects_tool_path():
    with Tapestry() as t:
        msg = Parameter(
            "msg",
            dict,
            default={"type": "tool", "name": "search"},
            _config=KnotConfig(id="msg"),
        )
        b = Branch(
            input=msg,
            selector=lambda p: "tool" if p["type"] == "tool" else "resp",
            branches=("tool", "resp"),
            _config=KnotConfig(id="route"),
        )
        handle_tool(p=b["tool"], _config=KnotConfig(id="h_tool"))
        handle_resp(p=b["resp"], _config=KnotConfig(id="h_resp"))

    result = await t.run(RunRequest())
    assert result.outputs.get("h_tool") == "tool:search"
    # h_resp was not selected, so it's skipped, not in outputs.
    assert "h_resp" not in result.outputs
    assert "h_resp" in result.skipped


async def test_branch_selects_resp_path():
    with Tapestry() as t:
        msg = Parameter(
            "msg",
            dict,
            default={"type": "resp", "text": "hi"},
            _config=KnotConfig(id="msg"),
        )
        b = Branch(
            input=msg,
            selector=lambda p: "tool" if p["type"] == "tool" else "resp",
            branches=("tool", "resp"),
            _config=KnotConfig(id="route"),
        )
        handle_tool(p=b["tool"], _config=KnotConfig(id="h_tool"))
        handle_resp(p=b["resp"], _config=KnotConfig(id="h_resp"))

    result = await t.run(RunRequest())
    assert "h_tool" not in result.outputs
    assert result.outputs.get("h_resp") == "resp:hi"
    assert "h_tool" in result.skipped


async def test_branch_outputs_skipped_have_lineage():
    with Tapestry() as t:
        msg = Parameter(
            "msg",
            dict,
            default={"type": "tool", "name": "x"},
            _config=KnotConfig(id="msg"),
        )
        b = Branch(
            input=msg,
            selector=lambda p: p["type"],
            branches=("tool", "resp"),
            _config=KnotConfig(id="route"),
        )

    result = await t.run(RunRequest())
    by_id = {rec.knot_id: rec for rec in result.lineage}
    assert by_id["route:tool"].outcome == "ok"
    assert by_id["route:resp"].outcome == "skipped"
    assert by_id["route:resp"].skip_reason == "branch_not_selected"


def test_branch_requires_known_input_kwarg():
    with pytest.raises(TypeError):
        Branch(
            input="not a knot",  # type: ignore[arg-type]
            selector=lambda x: "a",
            branches=("a",),
            _config=KnotConfig(id="b"),
        )


def test_branch_rejects_duplicate_branches():
    p = Parameter("x", int)
    with pytest.raises(TypeError, match="duplicate"):
        Branch(
            input=p,
            selector=lambda x: "a",
            branches=("a", "a"),
            _config=KnotConfig(id="b"),
        )


def test_branch_getitem_unknown_raises():
    p = Parameter("x", int)
    b = Branch(
        input=p,
        selector=lambda x: "a",
        branches=("a", "b"),
        _config=KnotConfig(id="b"),
    )
    with pytest.raises(KeyError):
        b["c"]


async def test_branch_unknown_selection_fails():
    """Selector returns a name not in declared branches → Branch errors."""
    with Tapestry() as t:
        msg = Parameter("msg", dict, default={"type": "rogue"}, _config=KnotConfig(id="msg"))
        Branch(
            input=msg,
            selector=lambda p: "rogue",
            branches=("tool", "resp"),
            _config=KnotConfig(id="route"),
        )
    result = await t.run(RunRequest())
    assert not result.succeeded
    assert any(rec.knot_id == "route" for rec in result.exceptions)
