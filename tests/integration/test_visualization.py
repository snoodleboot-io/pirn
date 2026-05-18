"""Visualization tests."""

from __future__ import annotations

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.tapestry import Tapestry
from pirn.viz.html import html_for_run
from pirn.viz.mermaid import mermaid_for_run, mermaid_for_tapestry


@knot
async def _add(x: int, y: int) -> int:
    return x + y


@knot
async def _double(x: int) -> int:
    return x * 2


# ============================================================ Mermaid


def test_mermaid_for_tapestry_starts_with_graph_directive():
    with Tapestry() as t:
        Parameter("x", int, _config=KnotConfig(id="x"))
    output = mermaid_for_tapestry(t)
    assert output.startswith("graph TD")


def test_mermaid_for_tapestry_includes_all_knots():
    with Tapestry() as t:
        x = Parameter("x", int, _config=KnotConfig(id="x"))
        y = Parameter("y", int, _config=KnotConfig(id="y"))
        _add(x=x, y=y, _config=KnotConfig(id="sum"))
    output = mermaid_for_tapestry(t)
    assert "x[" in output
    assert "y[" in output
    assert "sum[" in output


def test_mermaid_for_tapestry_renders_edges():
    with Tapestry() as t:
        x = Parameter("x", int, _config=KnotConfig(id="x"))
        y = Parameter("y", int, _config=KnotConfig(id="y"))
        _add(x=x, y=y, _config=KnotConfig(id="sum"))
    output = mermaid_for_tapestry(t)
    assert "x --> sum" in output
    assert "y --> sum" in output


def test_mermaid_for_tapestry_sanitizes_special_characters_in_ids():
    with Tapestry() as t:
        Parameter("x", int, _config=KnotConfig(id="my-knot.with:special.chars"))
    output = mermaid_for_tapestry(t)
    # Hyphens/dots/colons get mapped to underscores so the node id is a valid mermaid identifier.
    assert "my_knot_with_special_chars" in output


async def test_mermaid_for_run_overlays_outcomes():
    with Tapestry() as t:
        x = Parameter("x", int, default=5, _config=KnotConfig(id="x"))
        _double(x=x, _config=KnotConfig(id="d"))
    result = await t.run(RunRequest())
    output = mermaid_for_run(result)

    # Both knots got class "ok".
    assert "class x ok;" in output
    assert "class d ok;" in output
    # Edge present.
    assert "x --> d" in output
    # Class definitions section is included.
    assert "classDef ok" in output


async def test_mermaid_for_run_marks_failed_knots():
    @knot
    async def boom(x: int) -> int:
        raise ValueError("oops")

    with Tapestry() as t:
        x = Parameter("x", int, default=1, _config=KnotConfig(id="x"))
        boom(x=x, _config=KnotConfig(id="b"))
    result = await t.run(RunRequest())
    output = mermaid_for_run(result)

    assert "class b err;" in output


# ============================================================ HTML


async def test_html_for_run_returns_complete_document():
    with Tapestry() as t:
        x = Parameter("x", int, default=5, _config=KnotConfig(id="x"))
        _double(x=x, _config=KnotConfig(id="d"))
    result = await t.run(RunRequest())
    html = html_for_run(result)

    assert html.startswith("<!doctype html>")
    assert html.rstrip().endswith("</html>")
    assert "<svg" in html
    assert "</svg>" in html


async def test_html_for_run_includes_run_id_in_summary():
    with Tapestry() as t:
        x = Parameter("x", int, default=5, _config=KnotConfig(id="x"))
        _double(x=x, _config=KnotConfig(id="d"))
    result = await t.run(RunRequest())
    html = html_for_run(result)

    assert result.run_id in html
    # Summary block exists with knot ids visible.
    assert "summary" in html
    assert "x" in html and "d" in html


async def test_html_for_run_marks_failed_run():
    @knot
    async def boom(x: int) -> int:
        raise ValueError("oops")

    with Tapestry() as t:
        x = Parameter("x", int, default=1, _config=KnotConfig(id="x"))
        boom(x=x, _config=KnotConfig(id="b"))
    result = await t.run(RunRequest())
    html = html_for_run(result)

    assert "FAILED" in html
    assert "status-failed" in html


async def test_html_for_run_with_custom_title():
    with Tapestry() as t:
        Parameter("x", int, default=1, _config=KnotConfig(id="x"))
    result = await t.run(RunRequest())
    html = html_for_run(result, title="Q3 Daily Sales Pipeline")

    assert "Q3 Daily Sales Pipeline" in html


async def test_html_for_run_renders_each_knot_as_svg_node():
    """Each knot in the run gets one SVG <g> group representing a node."""
    with Tapestry() as t:
        x = Parameter("x", int, default=5, _config=KnotConfig(id="x"))
        _double(x=x, _config=KnotConfig(id="d1"))
        _double(x=x, _config=KnotConfig(id="d2"))
    result = await t.run(RunRequest())
    html = html_for_run(result)

    # Three lineage records → three node groups.
    n_groups = html.count('<g transform="translate(')
    assert n_groups == 3


async def test_html_for_run_handles_empty_lineage():
    """Edge case: a run that produces no lineage records should still
    render valid HTML rather than blow up."""

    # Synthesize a run-like object minimally.  We can't easily make
    # the engine produce zero lineage, so build a result manually.
    from datetime import UTC, datetime

    from pirn.core.run_result import RunResult

    result = RunResult(
        run_id="empty",
        succeeded=True,
        terminals_requested=[],
        dispatcher="LocalDispatcher",
        outputs={},
        skipped=[],
        errors={},
        lineage=[],
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    html = html_for_run(result)
    assert html.startswith("<!doctype html>")
    assert "empty run" in html


# ============================================================ SubTapestry viz


async def test_mermaid_for_tapestry_uses_subroutine_shape_for_sub_tapestry():
    from typing import Any

    from pirn.nodes.sub_tapestry import SubTapestry

    class _Inner(SubTapestry):
        async def process(self, x: int, **_: Any) -> None:  # type: ignore[override]
            pass

    with Tapestry() as t:
        p = Parameter("x", int, default=1, _config=KnotConfig(id="x"))
        _Inner(x=p, _config=KnotConfig(id="sub"))

    output = mermaid_for_tapestry(t)
    # [[label]] is Mermaid's subroutine (double-bracket) shape
    assert "sub[[" in output


async def test_mermaid_for_tapestry_regular_knot_uses_normal_shape():
    with Tapestry() as t:
        Parameter("x", int, default=1, _config=KnotConfig(id="x"))
        _double(x=Parameter("x", int, _config=KnotConfig(id="x2")), _config=KnotConfig(id="d"))

    output = mermaid_for_tapestry(t)
    assert 'd["' in output or "d[" in output


@pytest.mark.skip(reason="knot-kind design gap — see planning/backlog/viz-knot-kind-design.md")
async def test_html_for_tapestry_marks_sub_tapestry_node():
    from typing import Any

    from pirn.nodes.sub_tapestry import SubTapestry
    from pirn.viz.html import html_for_tapestry

    class _Inner(SubTapestry):
        async def process(self, x: int, **_: Any) -> None:  # type: ignore[override]
            pass

    with Tapestry() as t:
        p = Parameter("x", int, default=1, _config=KnotConfig(id="x"))
        _Inner(x=p, _config=KnotConfig(id="sub"))

    output = html_for_tapestry(t)
    assert "sub-tapestry" in output


@pytest.mark.skip(reason="knot-kind design gap — see planning/backlog/viz-knot-kind-design.md")
async def test_html_for_run_marks_sub_tapestry_node():
    from typing import Any

    from pirn.nodes.sub_tapestry import SubTapestry

    class _Doubler(SubTapestry):
        async def process(self, value: int, **_: Any) -> Knot:
            p = Parameter("v", int, default=value)
            return _double(x=p, _config=KnotConfig(id="out"))

    with Tapestry() as t:
        src = Parameter("v", int, default=3, _config=KnotConfig(id="src"))
        _Doubler(value=src, _config=KnotConfig(id="sub", validate_io=False))

    result = await t.run(RunRequest())
    output = html_for_run(result)
    assert "sub-tapestry" in output
