"""``SourceShapes`` — the AST shape definitions the ratchets in this tree share.

Each ratchet used to key on a *name*: a class called ``RetryPolicy``, a method
called ``chat``, a module that imports ``CanonicalJson``. Deleting the name
emptied the ratchet while the shape it stood for lived on under another name.
Every definition here is a *shape* instead — what the code does, not what it
is called — so a rename cannot hide it.

The definitions (each one is a ``@staticmethod`` below; the docstring on each
is the authoritative wording):

* **collaborator await** — ``await <call>`` whose callee is not the enclosing
  object's own method: ``await store.put(...)``, ``await self._llm.chat(...)``,
  ``await thunk()``, ``await self._handlers[k](...)``. ``await self.m(...)``
  counts only when ``m`` is a sibling method that itself (transitively) awaits
  a collaborator, so a helper cannot launder the call. ``asyncio.*`` module
  calls and inherited ``self``/``super()`` methods (``self._run_inner``, the
  engine's own inner-run seam) are not collaborators.
* **hand-rolled fan-out** — a call to a task/concurrency scheduler primitive:
  ``gather``, ``create_task``, ``ensure_future``, ``as_completed``,
  ``TaskGroup``, ``create_task_group``, ``run_in_executor``,
  ``ThreadPoolExecutor``/``ProcessPoolExecutor``, or ``asyncio.wait``.
* **hand-rolled time bound** — ``asyncio.timeout``/``timeout_at``/``wait_for``
  (qualified on any receiver or bare-imported ``wait_for``/``timeout_at``),
  ``anyio.fail_after``/``move_on_after``.
* **hand-rolled retry loop** — a ``for``/``while`` loop containing a ``try``
  one of whose ``except`` handlers lets control fall back into the loop (its
  last statement is not ``break``/``return``/``raise``), where the loop does
  not walk distinct items: it is a ``while`` loop, or iterates ``range(...)``/
  ``count(...)``/``repeat(...)``, or its body sleeps. ``for item in items:
  try: ... except: continue`` skips bad items and is not a retry.
* **own concurrency primitive** — constructing anything whose name ends in
  ``Semaphore``, or a ``CapacityLimiter``.
* **clock pacing** — one function that both reads a clock
  (``monotonic``/``perf_counter``, or a zero-argument ``<x>.time()``) and sleeps: a hand-rolled
  admission pacer (a token bucket, a rate limiter).
* **ambient run state** — constructing a ``ContextVar``: run-scoped state
  beside core's ``RunContextVars``/``RunNesting``.
* **signature introspection** — ``inspect.signature``/``signature``/
  ``get_type_hints``/``get_annotations``: deriving an argument schema from a
  callable, which core's ``Knot.input_json_schema`` owns.
* **content hashing** — importing ``hashlib``, ``xxhash``, ``blake3`` or
  ``mmh3``: core's ``ContentHasher`` owns content identity.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from typing import ClassVar


class SourceShapes:
    """Name-free AST shape predicates shared by the ratchets."""

    _FAN_OUT_CALLS: ClassVar[frozenset[str]] = frozenset(
        {
            "gather",
            "create_task",
            "ensure_future",
            "as_completed",
            "TaskGroup",
            "create_task_group",
            "run_in_executor",
            "ThreadPoolExecutor",
            "ProcessPoolExecutor",
        }
    )
    _TIME_BOUND_CALLS: ClassVar[frozenset[str]] = frozenset(
        {"timeout", "timeout_at", "wait_for", "fail_after", "move_on_after"}
    )
    _BARE_TIME_BOUND_CALLS: ClassVar[frozenset[str]] = frozenset(
        {"timeout_at", "wait_for", "fail_after", "move_on_after"}
    )
    _ATTEMPT_ITERATORS: ClassVar[frozenset[str]] = frozenset({"range", "count", "repeat"})
    _CLOCK_CALLS: ClassVar[frozenset[str]] = frozenset(
        {"monotonic", "perf_counter", "monotonic_ns", "perf_counter_ns"}
    )
    _SIGNATURE_CALLS: ClassVar[frozenset[str]] = frozenset(
        {"signature", "get_type_hints", "get_annotations"}
    )
    _HASHING_MODULES: ClassVar[frozenset[str]] = frozenset({"hashlib", "xxhash", "blake3", "mmh3"})
    _SCOPE_NODES: ClassVar[tuple[type[ast.AST], ...]] = (
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.Lambda,
        ast.ClassDef,
    )

    # -- traversal ---------------------------------------------------------

    @staticmethod
    def call_name(call: ast.Call) -> str | None:
        """Return the final identifier of ``call``'s callee (``put`` for ``a.b.put()``)."""
        func = call.func
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            return func.attr
        return None

    @staticmethod
    def scoped_walk(node: ast.AST) -> Iterator[ast.AST]:
        """Yield every descendant of ``node`` without entering a nested def/lambda/class."""
        for child in ast.iter_child_nodes(node):
            yield child
            if not isinstance(child, SourceShapes._SCOPE_NODES):
                yield from SourceShapes.scoped_walk(child)

    @staticmethod
    def scopes(node: ast.AST) -> Iterator[ast.AST]:
        """Yield ``node`` and every function/lambda nested anywhere inside it."""
        yield node
        for child in ast.walk(node):
            if child is not node and isinstance(
                child, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda
            ):
                yield child

    # -- collaborator awaits -------------------------------------------------

    @staticmethod
    def _is_self(expr: ast.expr) -> bool:
        if isinstance(expr, ast.Name) and expr.id in {"self", "cls"}:
            return True
        return (
            isinstance(expr, ast.Call)
            and isinstance(expr.func, ast.Name)
            and expr.func.id in {"super", "type"}
        )

    @staticmethod
    def self_method_called(call: ast.Call) -> str | None:
        """Return ``m`` when ``call`` is ``self.m(...)``/``super().m(...)``, else ``None``."""
        func = call.func
        if isinstance(func, ast.Attribute) and SourceShapes._is_self(func.value):
            return func.attr
        return None

    @staticmethod
    def is_collaborator_call(call: ast.Call, effectful_siblings: frozenset[str]) -> bool:
        """Whether awaiting ``call`` awaits some other object's work.

        See the module docstring: ``self.m()`` only when ``m`` is an effectful
        sibling; ``asyncio.<fn>()`` never.
        """
        own = SourceShapes.self_method_called(call)
        if own is not None:
            return own in effectful_siblings
        func = call.func
        return not (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "asyncio"
        )

    @staticmethod
    def _awaits_collaborator(node: ast.AST, effectful_siblings: frozenset[str]) -> bool:
        return any(
            isinstance(sub, ast.Await)
            and isinstance(sub.value, ast.Call)
            and SourceShapes.is_collaborator_call(sub.value, effectful_siblings)
            for sub in ast.walk(node)
        )

    @staticmethod
    def effectful_methods(
        methods: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    ) -> frozenset[str]:
        """Return the sibling methods that (transitively) await a collaborator."""
        effectful: frozenset[str] = frozenset()
        while True:
            grown = frozenset(
                name
                for name, method in methods.items()
                if SourceShapes._awaits_collaborator(method, effectful)
            )
            if grown == effectful:
                return effectful
            effectful = grown

    @staticmethod
    def loop_awaits_collaborator(node: ast.AST, effectful_siblings: frozenset[str]) -> bool:
        """Whether a loop or comprehension in any scope of ``node`` awaits a collaborator.

        A loop only counts the awaits in its own scope: a coroutine *defined*
        inside a loop and fanned out elsewhere is not awaited by the loop.
        """
        for scope in SourceShapes.scopes(node):
            for loop in SourceShapes.scoped_walk(scope):
                if not isinstance(
                    loop,
                    ast.For
                    | ast.AsyncFor
                    | ast.While
                    | ast.ListComp
                    | ast.SetComp
                    | ast.DictComp
                    | ast.GeneratorExp,
                ):
                    continue
                for inner in SourceShapes._per_iteration_nodes(loop):
                    if (
                        isinstance(inner, ast.Await)
                        and isinstance(inner.value, ast.Call)
                        and SourceShapes.is_collaborator_call(inner.value, effectful_siblings)
                    ):
                        return True
        return False

    @staticmethod
    def _per_iteration_nodes(loop: ast.AST) -> Iterator[ast.AST]:
        """Yield the nodes a loop evaluates once per iteration (not its first iterable)."""
        if isinstance(loop, ast.For | ast.AsyncFor):
            parts: list[ast.AST] = [*loop.body, *loop.orelse]
        elif isinstance(loop, ast.While):
            parts = [loop.test, *loop.body, *loop.orelse]
        elif isinstance(loop, ast.DictComp):
            parts = [loop.key, loop.value, *SourceShapes._comprehension_rest(loop.generators)]
        elif isinstance(loop, ast.ListComp | ast.SetComp | ast.GeneratorExp):
            parts = [loop.elt, *SourceShapes._comprehension_rest(loop.generators)]
        else:
            parts = []
        for part in parts:
            yield part
            if not isinstance(part, SourceShapes._SCOPE_NODES):
                yield from SourceShapes.scoped_walk(part)

    @staticmethod
    def _comprehension_rest(generators: list[ast.comprehension]) -> list[ast.AST]:
        first, *rest = generators
        parts: list[ast.AST] = [*first.ifs]
        for generator in rest:
            parts.extend([generator.iter, *generator.ifs])
        return parts

    # -- scheduling, time, retry ---------------------------------------------

    @staticmethod
    def fans_out_by_hand(node: ast.AST) -> bool:
        """Whether ``node`` calls a task/concurrency scheduler primitive."""
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            name = SourceShapes.call_name(sub)
            if name in SourceShapes._FAN_OUT_CALLS:
                return True
            func = sub.func
            if (
                name == "wait"
                and isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "asyncio"
            ):
                return True
        return False

    @staticmethod
    def bounds_time_by_hand(node: ast.AST) -> bool:
        """Whether ``node`` wraps work in a hand-rolled timeout."""
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            func = sub.func
            if isinstance(func, ast.Attribute) and func.attr in SourceShapes._TIME_BOUND_CALLS:
                return True
            if isinstance(func, ast.Name) and func.id in SourceShapes._BARE_TIME_BOUND_CALLS:
                return True
        return False

    @staticmethod
    def _resumes_loop(handler: ast.ExceptHandler) -> bool:
        last = handler.body[-1]
        return not isinstance(last, ast.Break | ast.Return | ast.Raise)

    @staticmethod
    def _sleeps(node: ast.AST) -> bool:
        return any(
            isinstance(sub, ast.Call) and SourceShapes.call_name(sub) == "sleep"
            for sub in SourceShapes.scoped_walk(node)
        )

    @staticmethod
    def is_retry_loop(loop: ast.AST) -> bool:
        """Whether ``loop`` is a hand-rolled retry loop (see the module docstring)."""
        if not isinstance(loop, ast.For | ast.AsyncFor | ast.While):
            return False
        resumes = any(
            isinstance(sub, ast.Try | ast.TryStar)
            and any(SourceShapes._resumes_loop(handler) for handler in sub.handlers)
            for sub in SourceShapes.scoped_walk(loop)
        )
        if not resumes:
            return False
        if isinstance(loop, ast.While) or SourceShapes._sleeps(loop):
            return True
        iterator = loop.iter
        return (
            isinstance(iterator, ast.Call)
            and SourceShapes.call_name(iterator) in SourceShapes._ATTEMPT_ITERATORS
        )

    @staticmethod
    def has_retry_loop(node: ast.AST) -> bool:
        """Whether any scope of ``node`` contains a hand-rolled retry loop."""
        return any(SourceShapes.is_retry_loop(sub) for sub in ast.walk(node))

    @staticmethod
    def constructs_concurrency_primitive(node: ast.AST) -> bool:
        """Whether ``node`` constructs a private in-flight budget."""
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                name = SourceShapes.call_name(sub) or ""
                if name.endswith("Semaphore") or name == "CapacityLimiter":
                    return True
        return False

    @staticmethod
    def paces_by_clock(node: ast.AST) -> bool:
        """Whether one function scope in ``node`` both reads a monotonic clock and sleeps."""
        for scope in SourceShapes.scopes(node):
            calls = [sub for sub in SourceShapes.scoped_walk(scope) if isinstance(sub, ast.Call)]
            names = {SourceShapes.call_name(call) for call in calls}
            reads_clock = bool(names & SourceShapes._CLOCK_CALLS) or any(
                isinstance(call.func, ast.Attribute) and call.func.attr == "time" and not call.args
                for call in calls
            )
            if reads_clock and "sleep" in names:
                return True
        return False

    # -- ambient state, schemas, hashing ---------------------------------------

    @staticmethod
    def constructs_context_var(node: ast.AST) -> bool:
        """Whether ``node`` constructs a ``ContextVar``."""
        return any(
            isinstance(sub, ast.Call) and SourceShapes.call_name(sub) == "ContextVar"
            for sub in ast.walk(node)
        )

    @staticmethod
    def introspects_signature(node: ast.AST) -> bool:
        """Whether ``node`` derives parameters from a callable's signature or hints."""
        return any(
            isinstance(sub, ast.Call)
            and SourceShapes.call_name(sub) in SourceShapes._SIGNATURE_CALLS
            for sub in ast.walk(node)
        )

    @staticmethod
    def imports_hashing(tree: ast.AST) -> frozenset[str]:
        """Return the content-hashing modules ``tree`` imports."""
        found: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(
                    alias.name.split(".")[0]
                    for alias in node.names
                    if alias.name.split(".")[0] in SourceShapes._HASHING_MODULES
                )
            elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
                root = node.module.split(".")[0]
                if root in SourceShapes._HASHING_MODULES:
                    found.add(root)
        return frozenset(found)
