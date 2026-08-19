"""Run/knot correlation stamped onto spans (PIR-798).

Agent spans otherwise reach a collector as an unattributable forest: nothing on
them says which pirn run produced them, so they cannot be lined up against the
core lineage stream keyed by the same id.

The two halves are stamped from different places on purpose, and that split is
what these tests pin:

* ``run_id`` is **ambient** — the engine sets a contextvar for the duration of a
  run — so :class:`Tracer` reads it for every span it opens.
* ``knot_id`` is **not**. Core has no ``_current_knot_id`` contextvar, so there
  is nothing to read and it must be supplied per call site.
"""

from __future__ import annotations

import pytest
from pirn.tapestry import _current_run_id

from pirn_agents.observability.span import Span
from pirn_agents.observability.span_emitting_tool_invocation_hook import (
    SpanEmittingToolInvocationHook,
)
from pirn_agents.observability.tracer import Tracer
from pirn_agents.tools.tool_status import ToolStatus
from tests.observability._recording_sink import RecordingSink


class _Run:
    """Bind an ambient run id for the block, as the engine does."""

    def __init__(self, run_id: str) -> None:
        self._run_id = run_id
        self._token: object | None = None

    def __enter__(self) -> _Run:
        self._token = _current_run_id.set(self._run_id)
        return self

    def __exit__(self, *_: object) -> None:
        _current_run_id.reset(self._token)  # type: ignore[arg-type]


def _only_span(sink: RecordingSink) -> Span:
    """Return the single span the sink saw, asserting there was exactly one."""
    assert len(sink.started) == 1
    return sink.started[0]


class TestRunIdIsStampedFromTheAmbientRun:
    def test_a_span_opened_inside_a_run_carries_its_id(self) -> None:
        sink = RecordingSink()
        with _Run("run-abc"):
            Tracer(sink).start_span(name="work").finish()
        assert _only_span(sink).attributes["pirn.run_id"] == "run-abc"

    def test_outside_a_run_the_key_is_omitted_not_none(self) -> None:
        # A span must never carry an attribute asserting it belongs to no run —
        # that is worse than silence for a collector grouping by run id.
        sink = RecordingSink()
        Tracer(sink).start_span(name="work").finish()
        assert "pirn.run_id" not in _only_span(sink).attributes

    def test_every_span_is_stamped_not_only_roots(self) -> None:
        # A child arriving at a collector on its own is still correlatable,
        # without walking to its root.
        sink = RecordingSink()
        tracer = Tracer(sink)
        with _Run("run-abc"):
            outer = tracer.start_span(name="outer")
            inner = tracer.start_span(name="inner")
            inner.finish()
            outer.finish()
        spans = sink.started
        assert [s.attributes.get("pirn.run_id") for s in spans] == ["run-abc", "run-abc"]
        assert [s.parent_id is None for s in spans] == [True, False]

    def test_an_explicit_run_id_beats_the_ambient_one(self) -> None:
        # Lets a span be re-attributed when reconstructed away from its run.
        sink = RecordingSink()
        with _Run("run-abc"):
            Tracer(sink).start_span(name="work", attributes={"pirn.run_id": "explicit"}).finish()
        assert _only_span(sink).attributes["pirn.run_id"] == "explicit"

    def test_the_run_id_does_not_leak_after_the_run_ends(self) -> None:
        sink = RecordingSink()
        tracer = Tracer(sink)
        with _Run("run-abc"):
            tracer.start_span(name="inside").finish()
        tracer.start_span(name="after").finish()
        spans = sink.started
        assert spans[0].attributes.get("pirn.run_id") == "run-abc"
        assert "pirn.run_id" not in spans[1].attributes


class TestKnotIdIsSuppliedPerCallSite:
    def test_the_hook_stamps_the_knot_id_it_was_built_with(self) -> None:
        sink = RecordingSink()
        hook = SpanEmittingToolInvocationHook(Tracer(sink), knot_id="executor-1")
        hook.on_start(tool_name="search", args_digest="d1", call_id="c1")
        assert _only_span(sink).attributes["pirn.knot_id"] == "executor-1"

    def test_without_one_the_key_is_omitted(self) -> None:
        # MapAgent and friends are not Knots and have no identity to give.
        sink = RecordingSink()
        hook = SpanEmittingToolInvocationHook(Tracer(sink))
        hook.on_start(tool_name="search", args_digest="d1", call_id="c1")
        assert "pirn.knot_id" not in _only_span(sink).attributes

    def test_a_non_str_knot_id_is_rejected_at_construction(self) -> None:
        with pytest.raises(TypeError, match="knot_id"):
            SpanEmittingToolInvocationHook(Tracer(RecordingSink()), knot_id=7)  # type: ignore[arg-type]

    def test_a_tool_span_carries_both_halves_together(self) -> None:
        # The point of the ticket: one span, correlatable to both the run and
        # the knot that produced it.
        sink = RecordingSink()
        hook = SpanEmittingToolInvocationHook(Tracer(sink), knot_id="executor-1")
        with _Run("run-abc"):
            hook.on_start(tool_name="search", args_digest="d1", call_id="c1")
            hook.on_finish(tool_name="search", call_id="c1", status=ToolStatus.OK, latency=0.25)
        attributes = _only_span(sink).attributes
        assert attributes["pirn.run_id"] == "run-abc"
        assert attributes["pirn.knot_id"] == "executor-1"
        assert attributes["tool.name"] == "search"
