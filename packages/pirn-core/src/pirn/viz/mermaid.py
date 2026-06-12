"""Mermaid renderers.

Mermaid is the de-facto standard for embeddable graph diagrams in
Markdown.  GitHub, GitLab, MkDocs, Notion, and most modern doc tools
render fenced ``mermaid`` blocks natively.

The output uses ``graph TD`` (top-down) layout because pipelines read
naturally from inputs at the top to outputs at the bottom.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult
    from pirn.tapestry import Tapestry


class MermaidRenderer:
    """Render tapestries and run results to Mermaid graph syntax."""

    # Mermaid class definitions for outcome-colored nodes.  Picked to be
    # legible in both light and dark themes.
    _class_defs: ClassVar[str] = (
        "classDef ok fill:#d1f4d4,stroke:#2d8a39,color:#1b3d1f;\n"
        "    classDef err fill:#fbd5d5,stroke:#a52a2a,color:#3d1010;\n"
        "    classDef skipped fill:#e7e7e7,stroke:#888,color:#333;\n"
        "    classDef pending fill:#fff3c4,stroke:#b48a14,color:#3d2e08;"
    )

    @classmethod
    def for_tapestry(cls, tapestry: Tapestry) -> str:
        """Render a tapestry's structure as Mermaid graph syntax.

        No status overlay; just the topology.  Use ``for_run`` for
        a status-colored variant.  SubTapestry knots use the Mermaid
        subroutine shape (double brackets) to signal they contain an inner
        pipeline.
        """
        from pirn.nodes.sub_tapestry import SubTapestry

        knots = tapestry.store.all()
        lines = ["graph TD"]
        for knot in knots:
            node_id = cls._safe_node_id(knot.knot_id)
            label = cls._node_label(knot.knot_id, type(knot).__name__)
            if isinstance(knot, SubTapestry):
                lines.append(f'    {node_id}[["{label}"]]')
            else:
                lines.append(f'    {node_id}["{label}"]')
        for knot in knots:
            for parent in knot.parents.values():
                parent_id = cls._safe_node_id(parent.knot_id)
                child_id = cls._safe_node_id(knot.knot_id)
                lines.append(f"    {parent_id} --> {child_id}")
        return "\n".join(lines)

    @classmethod
    def for_run(cls, result: RunResult) -> str:
        """Render a run's result as Mermaid with status overlay.

        Each knot is colored by outcome:

        * green - ``ok``
        * red - ``err``
        * grey - ``skipped``
        * yellow - not present (run didn't reach it)
        """
        lines = ["graph TD"]
        seen_edges: set[tuple[str, str]] = set()

        # Map knot_id -> outcome from the lineage records.
        outcomes = {rec.knot_id: rec.outcome for rec in result.lineage}

        # Build nodes from lineage records.
        for rec in result.lineage:
            node_id = cls._safe_node_id(rec.knot_id)
            label = cls._node_label(rec.knot_id, cls._short_class(rec.knot_class))
            lines.append(f'    {node_id}["{label}"]')

        # Edges come from parent_input_hashes; we need to resolve which
        # other lineage record produced each input hash, so we build a
        # reverse index.
        by_output: dict[str, str] = {}
        for rec in result.lineage:
            if rec.output_hash is not None:
                by_output[rec.output_hash] = rec.knot_id

        for rec in result.lineage:
            for input_hash in rec.parent_input_hashes.values():
                parent_kid = by_output.get(input_hash)
                if parent_kid is None:
                    continue
                edge = (parent_kid, rec.knot_id)
                if edge in seen_edges:
                    continue
                seen_edges.add(edge)
                lines.append(
                    f"    {cls._safe_node_id(parent_kid)} --> {cls._safe_node_id(rec.knot_id)}"
                )

        # Apply classes per node.
        for kid, outcome in outcomes.items():
            css = outcome if outcome in ("ok", "err", "skipped") else "pending"
            lines.append(f"    class {cls._safe_node_id(kid)} {css};")

        lines.append("")
        lines.append(cls._class_defs)
        return "\n".join(lines)

    @staticmethod
    def _safe_node_id(knot_id: str) -> str:
        """Mermaid identifiers can't contain certain characters; sanitize."""
        safe = []
        for ch in knot_id:
            if ch.isalnum() or ch == "_":
                safe.append(ch)
            else:
                safe.append("_")
        sanitized = "".join(safe)
        if not sanitized:
            sanitized = "_"
        if sanitized[0].isdigit():
            sanitized = "n_" + sanitized
        return sanitized

    @staticmethod
    def _node_label(knot_id: str, class_name: str) -> str:
        # Mermaid escapes are minimal; quote the label and avoid embedded
        # double quotes.
        safe_id = knot_id.replace('"', "'")
        safe_class = class_name.replace('"', "'")
        return f"{safe_id}<br/>({safe_class})"

    @staticmethod
    def _short_class(qualname: str) -> str:
        """Last segment of a dotted qualname."""
        return qualname.rsplit(".", 1)[-1]


def mermaid_for_tapestry(tapestry: Tapestry) -> str:
    """Public wrapper around :meth:`MermaidRenderer.for_tapestry`."""
    return MermaidRenderer.for_tapestry(tapestry)


def mermaid_for_run(result: RunResult) -> str:
    """Public wrapper around :meth:`MermaidRenderer.for_run`."""
    return MermaidRenderer.for_run(result)
