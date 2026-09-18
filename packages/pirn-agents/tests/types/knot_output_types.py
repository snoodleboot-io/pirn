"""``KnotOutputTypes`` — what every knot in ``pirn_agents`` is annotated to hand back.

ADR agents-speaks-core WS6b: a value that crosses a knot boundary is a
``Payload[Frame, Data]`` — data plus a frame describing its lineage and metadata,
with ``derive()`` to carry that forward. A flat frozen dataclass crossing the
same boundary carries the data and nothing else.

Scope is the *shape*, not a module list. The ratchet this feeds used to walk
``pirn_agents/types/`` and then check a pinned list of twenty-three
``*Result``/``*Frame`` modules, so every non-``Payload`` result type defined
anywhere else was invisible to it. Here the subject is every ``Knot`` in the
package (see :class:`~tests.agents_source_index.AgentsSourceIndex`), the
question is what its own ``process()`` is annotated to return, and the answer is
resolved against the package's class index — so a type is found wherever it is
defined and whatever it is called.

Types core owns, and builtins, do not resolve in the agents index and are core's
business; a knot that returns another knot is declaring a graph, not handing back
a value.
"""

from __future__ import annotations

import ast

from pirn.core.knot import Knot
from pirn.core.payload import Payload
from pirn.core.pirn_opaque_value import PirnOpaqueValue

from tests.agents_source_index import AgentsSourceIndex
from tests.source_shapes import SourceShapes


class KnotOutputTypes:
    """Resolves what every knot's ``process()`` is annotated to return."""

    @staticmethod
    def annotated_type_names(node: ast.ClassDef) -> frozenset[str]:
        """Return the type names in the class's own ``process()`` return annotation.

        Every identifier in the annotation counts, so a container
        (``tuple[ToolResult, ...]``, ``ToolResult | None``) is read as the types
        it carries — a container of non-``Payload`` values crosses the boundary
        just as a bare one does.
        """
        process = SourceShapes.methods_of(node).get("process")
        if process is None or process.returns is None:
            return frozenset()
        return KnotOutputTypes._names_in(process.returns)

    @staticmethod
    def _names_in(annotation: ast.expr) -> frozenset[str]:
        """Return the trailing identifiers naming a type in ``annotation``.

        A dotted name yields only its final component (``Plan`` for
        ``plan.Plan``): the module prefix is not a type.
        """
        if isinstance(annotation, ast.Name):
            return frozenset({annotation.id})
        if isinstance(annotation, ast.Attribute):
            return frozenset({annotation.attr})
        return frozenset(
            name
            for child in ast.iter_child_nodes(annotation)
            if isinstance(child, ast.expr)
            for name in KnotOutputTypes._names_in(child)
        )

    @staticmethod
    def is_boundary_value(subject: type) -> bool:
        """Whether ``subject`` is a value that crosses a knot boundary.

        A ``Knot`` is a graph node the engine runs, not a value handed back.
        """
        return not issubclass(subject, Knot)

    @staticmethod
    def is_payload_or_frame(subject: type) -> bool:
        """Whether ``subject`` is a ``Payload`` or a frame carried as one's metadata."""
        if issubclass(subject, Payload):
            return True
        return subject.__name__.endswith("Frame") and issubclass(subject, PirnOpaqueValue)

    @staticmethod
    def offending_outputs_of(
        node: ast.ClassDef, by_name: dict[str, tuple[str, type, ast.ClassDef]]
    ) -> frozenset[str]:
        """Return the labels of ``node``'s output types that are neither Payload nor frame.

        ``by_name`` resolves a name written in an annotation to the class it
        names; a name it does not hold is a builtin or a core type, which is
        not this package's to shape.
        """
        found: set[str] = set()
        for name in KnotOutputTypes.annotated_type_names(node):
            entry = by_name.get(name)
            if entry is None:
                continue
            type_label, subject, _type_node = entry
            if KnotOutputTypes.is_boundary_value(subject) and not (
                KnotOutputTypes.is_payload_or_frame(subject)
            ):
                found.add(type_label)
        return frozenset(found)

    @staticmethod
    def discover() -> dict[str, frozenset[str]]:
        """Return ``{"type label": {knot label, ...}}`` for every offending output type."""
        by_name = AgentsSourceIndex.classes_by_name()
        found: dict[str, set[str]] = {}
        for knot_label, (_knot, node) in AgentsSourceIndex.knots().items():
            for type_label in KnotOutputTypes.offending_outputs_of(node, by_name):
                found.setdefault(type_label, set()).add(knot_label)
        return {label: frozenset(knots) for label, knots in found.items()}
