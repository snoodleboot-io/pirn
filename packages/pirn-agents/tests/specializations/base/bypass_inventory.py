"""``BypassInventory`` — find every ``Knot`` in ``pirn_agents`` and classify
known engine-bypass shapes in its ``process()`` body.

Shared by ``test_no_engine_bypass.py`` (the frozen ratchet asserted by exact
equality) and ``regen_bypass_allowlist.py`` (the CLI that recomputes the
allowlists after a merge). Keeping the walk and the detectors here means both
consumers see the same answer for "what does the tree look like right now" —
the ratchet only has to compare that answer against what it froze.

PIR-856 widened the walk from "``SubTapestry`` subclasses under
``specializations/``" to "every ``Knot`` subclass anywhere in
``pirn_agents``", because a bypass is a property of ``process()``, not of
where a class lives or which base it names. The class-membership scan is
still runtime ``issubclass`` (not AST), for the same reason the original did
it that way: a renamed base cannot silently drop a class out of scope.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path
from typing import ClassVar

from pirn.core.knot import Knot

import pirn_agents


class BypassInventory:
    """Discovers every Knot's own ``process()`` and classifies its bypass shapes."""

    #: Method names whose direct, unretried call inside a loop is the shape
    #: this ticket calls out: an LLM or tool call re-issued by hand rather
    #: than through a ``LoopSubTapestry`` iteration or a fan-out knot.
    _LOOP_CALL_NAMES: ClassVar[frozenset[str]] = frozenset({"chat", "complete", "invoke", "search"})

    @staticmethod
    def discover_process_methods() -> dict[str, ast.AST]:
        """Return ``{"relative/path.py::ClassName": process_ast}`` for every
        ``Knot`` subclass in ``pirn_agents`` that defines its own ``process()``.

        Membership is decided at runtime (``issubclass``) so a renamed base
        cannot silently drop a class out of scope; the body is read from the
        AST because that is the only place a bypass shape is visible. A class
        that inherits ``process()`` without overriding it (an abstract
        mid-tree base) contributes no entry — there is no body of its own to
        scan.
        """
        root = Path(pirn_agents.__path__[0])
        found: dict[str, ast.AST] = {}

        for info in pkgutil.walk_packages(pirn_agents.__path__, pirn_agents.__name__ + "."):
            module = importlib.import_module(info.name)
            module_file = getattr(module, "__file__", None)
            if module_file is None:
                continue
            owned = {
                obj.__qualname__
                for name in dir(module)
                if isinstance(obj := getattr(module, name), type)
                and issubclass(obj, Knot)
                and obj.__module__ == info.name
            }
            if not owned:
                continue
            rel = Path(module_file).relative_to(root)
            tree = ast.parse(Path(module_file).read_text())
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef) or node.name not in owned:
                    continue
                process = next(
                    (
                        child
                        for child in node.body
                        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
                        and child.name == "process"
                    ),
                    None,
                )
                if process is not None:
                    found[f"{rel}::{node.name}"] = process
        return dict(sorted(found.items()))

    @staticmethod
    def awaits_child_process(process: ast.AST) -> bool:
        """True if the body awaits some *other* object's ``process()``."""
        for node in ast.walk(process):
            if not (isinstance(node, ast.Await) and isinstance(node.value, ast.Call)):
                continue
            func = node.value.func
            if not (isinstance(func, ast.Attribute) and func.attr == "process"):
                continue
            receiver = func.value
            is_self = isinstance(receiver, ast.Name) and receiver.id == "self"
            is_super = (
                isinstance(receiver, ast.Call) and getattr(receiver.func, "id", "") == "super"
            )
            if not (is_self or is_super):
                return True
        return False

    @staticmethod
    def returns_inline_source(process: ast.AST) -> bool:
        """True if the returned sink is a ``Source`` subclass defined in the body.

        Only the *returned* one counts. A locally-defined ``Source`` that
        seeds a real graph is legitimate, and flagging it would make this
        guard something authors route around rather than obey.
        """
        inline = {
            node.name
            for node in ast.walk(process)
            if isinstance(node, ast.ClassDef)
            and {base.id for base in node.bases if isinstance(base, ast.Name)} & {"Source"}
        }
        if not inline:
            return False
        return any(
            isinstance(node, ast.Return)
            and isinstance(node.value, ast.Call)
            and getattr(node.value.func, "id", None) in inline
            for node in ast.walk(process)
        )

    @staticmethod
    def opens_unrun_tapestry(process: ast.AST) -> bool:
        """True if a ``with Tapestry()`` is opened and never passed to ``_run_inner``."""
        opened: set[str] = set()
        executed: set[str] = set()
        for node in ast.walk(process):
            if isinstance(node, ast.With):
                for item in node.items:
                    expr = item.context_expr
                    if isinstance(expr, ast.Call) and getattr(expr.func, "id", "") == "Tapestry":
                        target = item.optional_vars
                        opened.add(target.id if isinstance(target, ast.Name) else "<unbound>")
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "_run_inner"
            ):
                executed.update(arg.id for arg in node.args if isinstance(arg, ast.Name))
        return bool(opened - executed)

    @staticmethod
    def awaits_invoke(process: ast.AST) -> bool:
        """True if the body awaits some object's ``invoke()`` directly.

        ``ToolInvocation.process()`` is the one sanctioned exception (it *is*
        the knot whose job is to make this call through the engine); every
        other hit is a call that bypasses ``ToolInvocation``/``Aggregator``
        fan-out and so leaves the call with no lineage row (PIR-856).
        """
        for node in ast.walk(process):
            if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
                func = node.value.func
                if isinstance(func, ast.Attribute) and func.attr == "invoke":
                    return True
        return False

    @staticmethod
    def uses_asyncio_gather(process: ast.AST) -> bool:
        """True if the body calls ``asyncio.gather`` (qualified or bare-imported)."""
        for node in ast.walk(process):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "gather":
                return True
            if isinstance(func, ast.Name) and func.id == "gather":
                return True
        return False

    @classmethod
    def loop_awaits_llm_or_tool_call(cls, process: ast.AST) -> bool:
        """True if a ``for``/``while`` loop body directly awaits an LLM/tool call.

        Nested function/lambda bodies are excluded: a loop that merely
        *defines* a per-item coroutine (later fanned out by the engine, e.g.
        via ``Aggregator`` or gathered elsewhere) is not itself re-issuing
        the call by hand — the loop constructing per-call knots in
        ``ParallelToolCaller.process()`` is exactly this shape and must not
        trip the detector.
        """
        for node in ast.walk(process):
            if not isinstance(node, ast.For | ast.While):
                continue
            for inner in ast.walk(node):
                if isinstance(inner, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
                    continue
                if isinstance(inner, ast.Await) and isinstance(inner.value, ast.Call):
                    func = inner.value.func
                    if isinstance(func, ast.Attribute) and func.attr in cls._LOOP_CALL_NAMES:
                        return True
        return False

    @staticmethod
    def hand_rolled_while_true_retry(process: ast.AST) -> bool:
        """True if the body contains a literal ``while True:`` loop.

        The structural marker every hand-rolled retry loop in this codebase
        was written with before ``RetryPolicy.run()`` existed (PIR-856); a
        caller that composes ``RetryPolicy.run()`` instead has no
        ``while True`` of its own.
        """
        for node in ast.walk(process):
            if (
                isinstance(node, ast.While)
                and isinstance(node.test, ast.Constant)
                and node.test.value is True
            ):
                return True
        return False
