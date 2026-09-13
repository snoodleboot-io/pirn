"""``ToolKnotInventory`` — find what the "a tool is a Knot" collapse burns down.

ADR "agents speaks core" WS1 turns ``Tool`` into a ``Knot`` class: the
capability is the class, one call is an instance, the outcome is the engine's
``Result``.  Three things in ``pirn_agents`` stand in the way and are what this
inventory counts:

* classes that carry their own execution verb — a method named ``invoke`` —
  beside ``Knot.process()``;
* modules that import the parallel outcome/schema/adapter vocabulary
  (``ToolResult``, ``ToolStatus``, ``ToolSchemaCompiler``,
  ``ArgumentValidator``, ``AgentTool``);
* call sites that await ``<x>.invoke(...)`` instead of wiring a knot.

Shared by ``test_tool_is_a_knot_ratchet.py`` (the frozen ratchet asserted by
exact equality) so the ratchet only compares "what the tree looks like now"
against what it froze.  Source-only AST pass over ``pirn_agents``; ``tests``
are never scanned.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import ClassVar

import pirn_agents


class ToolKnotInventory:
    """Discovers the ``invoke``/``ToolResult`` inventory across ``pirn_agents``."""

    #: Names whose import marks a module as speaking the parallel tool vocabulary.
    PARALLEL_NAMES: ClassVar[frozenset[str]] = frozenset(
        {"ToolResult", "ToolStatus", "ToolSchemaCompiler", "ArgumentValidator", "AgentTool"}
    )

    @staticmethod
    def _modules() -> list[tuple[str, ast.Module]]:
        root = Path(pirn_agents.__path__[0])
        found: list[tuple[str, ast.Module]] = []
        for path in sorted(root.rglob("*.py")):
            if any(part in {"tests", "__pycache__"} for part in path.parts):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            found.append((path.relative_to(root).as_posix(), tree))
        return found

    @staticmethod
    def defines_invoke(node: ast.ClassDef) -> bool:
        """Whether *node* defines a method named ``invoke`` in its own body."""
        return any(
            isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) and child.name == "invoke"
            for child in node.body
        )

    @classmethod
    def imports_parallel_name(cls, tree: ast.Module) -> frozenset[str]:
        """The parallel-vocabulary names *tree* imports (``from x import Name``)."""
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names.update(alias.name for alias in node.names if alias.name in cls.PARALLEL_NAMES)
        return frozenset(names)

    @classmethod
    def awaited_invoke_sites(cls, tree: ast.Module) -> set[str]:
        """Qualnames of every function/method body containing ``await <x>.invoke(...)``."""
        sites: set[str] = set()
        cls._collect_invoke_sites(tree, "", sites)
        return sites

    @classmethod
    def _collect_invoke_sites(cls, node: ast.AST, scope: str, sites: set[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
                cls._collect_invoke_sites(child, f"{scope}{child.name}.", sites)
                continue
            if (
                isinstance(child, ast.Await)
                and isinstance(child.value, ast.Call)
                and isinstance(child.value.func, ast.Attribute)
                and child.value.func.attr == "invoke"
            ):
                sites.add(scope.rstrip("."))
            cls._collect_invoke_sites(child, scope, sites)

    @classmethod
    def discover(cls) -> dict[str, frozenset[str]]:
        """Return the inventories keyed ``invoke_classes`` / ``importers`` / ``call_sites``."""
        invoke_classes: set[str] = set()
        importers: set[str] = set()
        call_sites: set[str] = set()
        for relative, tree in cls._modules():
            for node in tree.body:
                if isinstance(node, ast.ClassDef) and cls.defines_invoke(node):
                    invoke_classes.add(f"{relative}::{node.name}")
            if cls.imports_parallel_name(tree):
                importers.add(relative)
            call_sites.update(f"{relative}::{site}" for site in cls.awaited_invoke_sites(tree))
        return {
            "invoke_classes": frozenset(invoke_classes),
            "importers": frozenset(importers),
            "call_sites": frozenset(call_sites),
        }

    @classmethod
    def render(cls) -> str:
        """Return the three allowlists as pasteable Python source."""
        found = cls.discover()
        blocks: list[str] = []
        for key, constant in (
            ("invoke_classes", "INVOKE_CLASSES"),
            ("importers", "PARALLEL_VOCABULARY_IMPORTERS"),
            ("call_sites", "AWAITED_INVOKE_CALL_SITES"),
        ):
            lines = [f"{constant} = frozenset("]
            hits = sorted(found[key])
            if hits:
                lines.append("    {")
                lines.extend(f"        {hit!r}," for hit in hits)
                lines.append("    }")
            else:
                lines.append("    set()")
            lines.append(")")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)
