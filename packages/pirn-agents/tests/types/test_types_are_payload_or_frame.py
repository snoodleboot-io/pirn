"""Guard: every value a knot hands back is a ``Payload`` or a frame.

ADR agents-speaks-core WS6b: a value that crosses a knot boundary is a
``Payload[Frame, Data]`` — data plus a frame that describes its lineage and
metadata and supports ``derive()``. A flat frozen dataclass crossing the same
boundary carries the data and nothing else: no metadata descriptor, no lineage,
nothing to derive from, and nothing the next knot can trace the value back
through.

There are no inventories here. The version this replaced had two, both keyed on
names: a walk of ``pirn_agents/types/`` that let anything through if its
qualname appeared in a ten-entry structural-type inventory, and a *pinned list of
twenty-three modules* naming the ``*Result``/``*Frame`` pairs to check — which is
why at least eleven non-``Payload`` ``*Result`` classes living outside those
twenty-three modules were invisible to it. The rule does not depend on where a
type lives or what it is called: **every ``pirn_agents`` type a knot's
``process()`` is annotated to return is a ``Payload`` or a frame**. Return
annotations are read off the AST and resolved against the package's class index,
so a type is found wherever it is defined.

Types core owns, and builtins, are core's business and are not scanned; a knot
that returns another knot is declaring a graph, not handing back a value.
:class:`TestKnotOutputDetectorFires` proves the detector fires, so an empty
finding means an empty tree and not a blind detector.
"""

from __future__ import annotations

import ast
import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.payload import Payload
from pirn.core.pirn_opaque_value import PirnOpaqueValue

from tests.agents_source_index import AgentsSourceIndex
from tests.types.knot_output_types import KnotOutputTypes


class TestEveryKnotOutputIsPayloadOrFrame(unittest.TestCase):
    """Every value crossing a knot boundary is a Payload or a frame. Asserted."""

    def test_the_walk_is_not_vacuous(self) -> None:
        """A guard that scans nothing passes for the wrong reason."""
        annotated = [
            label
            for label, (_knot, node) in AgentsSourceIndex.knots().items()
            if KnotOutputTypes.annotated_type_names(node)
        ]
        assert len(annotated) >= 200, len(annotated)

    def test_no_knot_returns_a_type_that_is_neither_payload_nor_frame(self) -> None:
        found = KnotOutputTypes.discover()
        assert found == {}, {label: sorted(knots) for label, knots in found.items()}


class TestKnotOutputDetectorFires(unittest.TestCase):
    """The detector fires on the shape it names, and not on a Payload or a frame."""

    @staticmethod
    def _names(source: str) -> frozenset[str]:
        node = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef))
        return KnotOutputTypes.annotated_type_names(node)

    def test_rule_reads_a_bare_return_annotation(self) -> None:
        assert self._names(
            "class K:\n"
            "    async def process(self, x, **_) -> FailoverResult:\n"
            "        return self._result(x)\n"
        ) == frozenset({"FailoverResult"})

    def test_rule_reads_through_a_container_annotation(self) -> None:
        """A tuple of non-Payload values crosses the boundary just as a bare one does."""
        assert self._names(
            "class K:\n"
            "    async def process(self, x, **_) -> tuple[ToolResult, ...]:\n"
            "        return ()\n"
        ) == frozenset({"tuple", "ToolResult"})

    def test_rule_reads_through_a_union_annotation(self) -> None:
        assert self._names(
            "class K:\n"
            "    async def process(self, x, **_) -> JudgeVerdict | None:\n"
            "        return None\n"
        ) == frozenset({"JudgeVerdict"})

    def test_rule_reads_a_dotted_annotation(self) -> None:
        assert self._names(
            "class K:\n"
            "    async def process(self, x, **_) -> plan.Plan:\n"
            "        return plan.Plan()\n"
        ) == frozenset({"Plan"})

    def test_rule_sees_nothing_in_an_unannotated_process(self) -> None:
        assert self._names(
            "class K:\n    async def process(self, x, **_):\n        return x\n"
        ) == (frozenset())

    def test_rule_classifies_a_payload_as_acceptable(self) -> None:
        class _Body(Payload[Any, str]):
            """A value that crosses a knot boundary carrying frame and data."""

        assert KnotOutputTypes.is_payload_or_frame(_Body)

    def test_rule_classifies_a_named_frame_as_acceptable(self) -> None:
        class _GenerationFrame(PirnOpaqueValue):
            """Only ever a Payload's metadata."""

        assert KnotOutputTypes.is_payload_or_frame(_GenerationFrame)

    def test_rule_classifies_a_flat_dataclass_as_a_violation(self) -> None:
        class _CompactionResult:
            """A flat record with no frame and no derive()."""

        assert not KnotOutputTypes.is_payload_or_frame(_CompactionResult)

    def test_rule_treats_a_returned_knot_as_a_graph_node_not_a_value(self) -> None:
        class _Inner(Knot):
            """A sink a SubTapestry hands back for the engine to run."""

        assert not KnotOutputTypes.is_boundary_value(_Inner)

    # -- the whole rule, end to end on a synthetic index ------------------------

    @staticmethod
    def _index(*subjects: type) -> dict[str, tuple[str, type, ast.ClassDef]]:
        """Stand in for the package's class index with the given classes."""
        empty = ast.ClassDef(
            name="_", bases=[], keywords=[], body=[], decorator_list=[], type_params=[]
        )
        return {
            subject.__name__.lstrip("_"): (
                f"synthetic/{subject.__name__.lstrip('_').lower()}.py::"
                f"{subject.__name__.lstrip('_')}",
                subject,
                empty,
            )
            for subject in subjects
        }

    def test_rule_fires_on_a_knot_returning_a_flat_result_type(self) -> None:
        """The whole rule: annotation read, resolved, and reported."""

        class _CompactionResult:
            """A flat record with no frame and no derive()."""

        node = next(
            n
            for n in ast.parse(
                "class CompactionKnot:\n"
                "    async def process(self, items, **_) -> CompactionResult:\n"
                "        return self._compact(items)\n"
            ).body
            if isinstance(n, ast.ClassDef)
        )
        assert KnotOutputTypes.offending_outputs_of(node, self._index(_CompactionResult)) == (
            frozenset({"synthetic/compactionresult.py::CompactionResult"})
        )

    def test_rule_fires_on_a_flat_result_inside_a_container(self) -> None:
        class _ToolResult:
            """A flat record handed back by the tuple-ful."""

        node = next(
            n
            for n in ast.parse(
                "class Executor:\n"
                "    async def process(self, calls, **_) -> tuple[ToolResult, ...]:\n"
                "        return ()\n"
            ).body
            if isinstance(n, ast.ClassDef)
        )
        assert KnotOutputTypes.offending_outputs_of(node, self._index(_ToolResult)) == frozenset(
            {"synthetic/toolresult.py::ToolResult"}
        )

    def test_rule_reports_nothing_for_a_knot_returning_a_payload(self) -> None:
        class _ConversationPayload(Payload[Any, str]):
            """Frame plus data, the shape a knot boundary takes."""

        node = next(
            n
            for n in ast.parse(
                "class Writer:\n"
                "    async def process(self, message, **_) -> ConversationPayload:\n"
                "        return self._payload(message)\n"
            ).body
            if isinstance(n, ast.ClassDef)
        )
        assert (
            KnotOutputTypes.offending_outputs_of(node, self._index(_ConversationPayload))
            == frozenset()
        )
