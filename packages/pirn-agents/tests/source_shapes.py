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
  engine's own inner-run seam) are not collaborators, and neither is a method
  on **async plumbing the same scope constructed** — ``await queue.get()``
  where ``queue = asyncio.Queue()`` a few lines up, or ``await t.run(...)``
  where ``t = Tapestry(...)``. A collaborator is something the knot *delegates
  work to*, and it arrives from outside: a parameter, state, or ``self``.
  Awaiting a queue this scope made is awaiting delivery of results the engine
  already produced, and awaiting a tapestry this scope made is *using* the
  engine, not bypassing it. The qualifier is the local construction, not the
  name — an injected collaborator called ``queue`` still counts.
* **fan-out collaborator await** — a collaborator call handed to one of those
  fan-out primitives (``gather(store.put(a), store.put(b))``): the same calls
  a loop would await, one scheduling layer further from the engine.
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
* **keyed store surface** — an own attribute a class both writes under a
  run-time key (``self._x[key] = value``) and reads back under one
  (``self._x[key]``, ``self._x.get(key)``, ``.pop``, ``.setdefault``): a
  key→value store of its own beside core's ``DataStore``, whatever the
  methods around it are called (``register``/``get`` as much as ``put``/``get``).
* **own event channel** — an own attribute a class fills with a callable
  handed to one of its methods and later delivers to, by calling the elements
  it holds: a subscriber list of its own beside the run's emitters.
* **hand-rolled inner-run step** — a method that both loops over run-time data
  and awaits core's inner-run seam (``self._run_inner``), whether the run sits
  inside the loop (an engine round trip per item) or the loop builds the run's
  nodes (N siblings declared by hand). Core's awaitable ``LoopSubTapestry``
  step owns the iteration.
* **bare verdict** — a ``-> bool`` return annotation: a knot that computes a
  pass/fail verdict is core's ``Check`` role, not a value knot.
* **foreign private write** — assigning a ``_private`` attribute on anything
  that is not ``self``/``cls``/``super()``, the enclosing class, or a local
  derived from ``self`` in the same scope: configuring another object by
  reaching past its surface.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from typing import ClassVar


class SourceShapes:
    """Name-free AST shape predicates shared by the ratchets."""

    _fan_out_calls: ClassVar[frozenset[str]] = frozenset(
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
    _time_bound_calls: ClassVar[frozenset[str]] = frozenset(
        {"timeout", "timeout_at", "wait_for", "fail_after", "move_on_after"}
    )
    _bare_time_bound_calls: ClassVar[frozenset[str]] = frozenset(
        {"timeout_at", "wait_for", "fail_after", "move_on_after"}
    )
    _attempt_iterators: ClassVar[frozenset[str]] = frozenset({"range", "count", "repeat"})
    _clock_calls: ClassVar[frozenset[str]] = frozenset(
        {"monotonic", "perf_counter", "monotonic_ns", "perf_counter_ns"}
    )
    _signature_calls: ClassVar[frozenset[str]] = frozenset(
        {"signature", "get_type_hints", "get_annotations"}
    )
    _hashing_modules: ClassVar[frozenset[str]] = frozenset({"hashlib", "xxhash", "blake3", "mmh3"})
    #: The types ``pirn.core.run_context_vars.RunContextVars`` publishes ambiently.
    #: A ``ContextVar`` of one of these is a second copy of the run's own state.
    _core_ambient_types: ClassVar[frozenset[str]] = frozenset(
        {
            "Tapestry",
            "RunHistory",
            "Emitter",
            "EmitterErrorPolicy",
            "DataStore",
            "DataTransport",
            "RunNesting",
            "ExecutionPlane",
            "TapestryStore",
            "ConcurrencyLimits",
            "Admission",
        }
    )
    _keyed_readers: ClassVar[frozenset[str]] = frozenset({"get", "pop", "setdefault"})
    _collection_adders: ClassVar[frozenset[str]] = frozenset({"append", "add", "appendleft"})
    #: Core's published inner-run seam (``SubTapestry._run_inner``). A core
    #: name, not an agents one: the whole point of these shapes is that agents
    #: speaks core's vocabulary, so core's seam is the fixed point they key on.
    _inner_run_seam: ClassVar[str] = "_run_inner"
    _scope_nodes: ClassVar[tuple[type[ast.AST], ...]] = (
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
            if not isinstance(child, SourceShapes._scope_nodes):
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
    def is_collaborator_call(
        call: ast.Call,
        effectful_siblings: frozenset[str],
        plumbing: frozenset[str] = frozenset(),
    ) -> bool:
        """Whether awaiting ``call`` awaits some other object's work.

        See the module docstring: ``self.m()`` only when ``m`` is an effectful
        sibling; ``asyncio.<fn>()`` never; and a method on a name in
        ``plumbing`` never, because the scope built that object itself out of
        ``asyncio``/``Tapestry`` rather than being handed it.
        """
        own = SourceShapes.self_method_called(call)
        if own is not None:
            return own in effectful_siblings
        func = call.func
        if not isinstance(func, ast.Attribute) or not isinstance(func.value, ast.Name):
            return True
        return func.value.id != "asyncio" and func.value.id not in plumbing

    #: Framework types whose locally constructed instances are plumbing, not
    #: collaborators: awaiting a ``Tapestry`` this scope built *is* the engine
    #: running. ``asyncio``'s own primitives are recognised by their module.
    _plumbing_types: ClassVar[frozenset[str]] = frozenset({"Tapestry"})

    @staticmethod
    def async_plumbing_names(scope: ast.AST) -> frozenset[str]:
        """Return the names ``scope`` binds to async plumbing it constructed itself.

        A name assigned from ``asyncio.<Anything>()`` or from one of
        :attr:`_plumbing_types`. Only this scope's own assignments count, so a
        collaborator arriving as a parameter or off ``self`` is never mistaken
        for plumbing however it is named.
        """
        names: set[str] = set()
        for sub in SourceShapes.scoped_walk(scope):
            if isinstance(sub, ast.Assign):
                targets: list[ast.expr] = list(sub.targets)
            elif isinstance(sub, ast.AnnAssign):
                targets = [sub.target]
            else:
                continue
            if not isinstance(sub.value, ast.Call) or not SourceShapes._builds_plumbing(sub.value):
                continue
            names.update(target.id for target in targets if isinstance(target, ast.Name))
        return frozenset(names)

    @staticmethod
    def _builds_plumbing(call: ast.Call) -> bool:
        """Whether ``call`` constructs an ``asyncio`` primitive or a framework container."""
        func = call.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            return func.value.id == "asyncio"
        return isinstance(func, ast.Name) and func.id in SourceShapes._plumbing_types

    @staticmethod
    def _awaits_collaborator(node: ast.AST, effectful_siblings: frozenset[str]) -> bool:
        plumbing = SourceShapes.async_plumbing_names(node)
        return any(
            isinstance(sub, ast.Await)
            and isinstance(sub.value, ast.Call)
            and SourceShapes.is_collaborator_call(sub.value, effectful_siblings, plumbing)
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
            plumbing = SourceShapes.async_plumbing_names(scope)
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
                        and SourceShapes.is_collaborator_call(
                            inner.value, effectful_siblings, plumbing
                        )
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
            if not isinstance(part, SourceShapes._scope_nodes):
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
        return any(
            isinstance(sub, ast.Call) and SourceShapes._is_fan_out_call(sub)
            for sub in ast.walk(node)
        )

    @staticmethod
    def fan_out_awaits_collaborator(node: ast.AST, effectful_siblings: frozenset[str]) -> bool:
        """Whether a collaborator's work is handed to a fan-out primitive.

        ``gather(store.put(k), store.put(j))`` runs the same collaborator
        calls a loop would, one scheduling layer further from the engine, so
        it is the same shape as a loop that awaits them.
        """
        for scope in SourceShapes.scopes(node):
            plumbing = SourceShapes.async_plumbing_names(scope)
            for sub in SourceShapes.scoped_walk(scope):
                if not isinstance(sub, ast.Call) or not SourceShapes._is_fan_out_call(sub):
                    continue
                handed: list[ast.expr] = [*sub.args, *(keyword.value for keyword in sub.keywords)]
                for argument in handed:
                    for inner in SourceShapes._handed_calls(argument):
                        if SourceShapes.is_collaborator_call(inner, effectful_siblings, plumbing):
                            return True
        return False

    @staticmethod
    def _handed_calls(argument: ast.expr) -> Iterator[ast.Call]:
        """Yield the call(s) ``argument`` hands to a fan-out primitive, as coroutines.

        Only the *awaitable* an argument evaluates to counts, not every call
        nested anywhere inside it: ``gather(store.put(a))`` hands a coroutine,
        while ``create_task(t.run(RunRequest(x), observers=Own.build(y)))``
        hands one coroutine whose arguments happen to be constructed by calls.
        Walking the whole argument made those arguments look like fanned-out
        collaborator work (PIR-874).

        Unwraps the forms that still hand over coroutines: ``*splat``, a
        list/tuple/set of them, a comprehension producing them, and a
        redundant ``await``.
        """
        if isinstance(argument, ast.Starred):
            yield from SourceShapes._handed_calls(argument.value)
        elif isinstance(argument, ast.List | ast.Tuple | ast.Set):
            for element in argument.elts:
                yield from SourceShapes._handed_calls(element)
        elif isinstance(argument, ast.ListComp | ast.SetComp | ast.GeneratorExp):
            yield from SourceShapes._handed_calls(argument.elt)
        elif isinstance(argument, ast.Await):
            yield from SourceShapes._handed_calls(argument.value)
        elif isinstance(argument, ast.Call):
            yield argument

    @staticmethod
    def _is_fan_out_call(call: ast.Call) -> bool:
        name = SourceShapes.call_name(call)
        if name in SourceShapes._fan_out_calls:
            return True
        func = call.func
        return (
            name == "wait"
            and isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "asyncio"
        )

    @staticmethod
    def bounds_time_by_hand(node: ast.AST) -> bool:
        """Whether ``node`` wraps work in a hand-rolled timeout."""
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            func = sub.func
            if isinstance(func, ast.Attribute) and func.attr in SourceShapes._time_bound_calls:
                return True
            if isinstance(func, ast.Name) and func.id in SourceShapes._bare_time_bound_calls:
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
            and SourceShapes.call_name(iterator) in SourceShapes._attempt_iterators
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
            reads_clock = bool(names & SourceShapes._clock_calls) or any(
                isinstance(call.func, ast.Attribute) and call.func.attr == "time" and not call.args
                for call in calls
            )
            if reads_clock and "sleep" in names:
                return True
        return False

    # -- ambient state, schemas, hashing ---------------------------------------

    @staticmethod
    def constructs_context_var(node: ast.AST) -> bool:
        """Whether ``node`` keeps ambient state core already publishes.

        Core's ``RunContextVars`` is the run's ambient state and ``RunNesting`` /
        ``ExecutionPlane`` are read from it; a second variable carrying the same
        thing can disagree with core's, and the depth, admission and value-plane
        guards read core's.

        The rival is decided by *what the variable carries*, not by the fact of a
        ``ContextVar`` (PIR-874). Core publishes the tapestry, run id, history,
        emitters and their error policy, the data store, the transport, the
        nesting frame, the execution plane, the extensible store and the
        dispatching knot id — a variable annotated to carry one of those is a
        second copy of it. A variable carrying something core does *not* publish
        is not: a flag saying a container is reporting the current call, or a
        policy of the package's own, has no core counterpart to disagree with.

        An *unannotated* ``ContextVar`` fires as well. The rule cannot tell what it
        carries, and this package annotates its class attributes, so saying what a
        variable holds is what earns it a judgement on what it holds.
        """
        declared: list[ast.AnnAssign] = [
            sub
            for sub in ast.walk(node)
            if isinstance(sub, ast.AnnAssign)
            and "ContextVar" in SourceShapes._names_in(sub.annotation)
        ]
        if any(
            SourceShapes._names_in(sub.annotation) & SourceShapes._core_ambient_types
            for sub in declared
        ):
            return True
        annotated_values = {id(sub.value) for sub in declared if sub.value is not None}
        return any(
            isinstance(sub, ast.Call)
            and SourceShapes.call_name(sub) == "ContextVar"
            and id(sub) not in annotated_values
            for sub in ast.walk(node)
        )

    @staticmethod
    def _names_in(annotation: ast.expr) -> frozenset[str]:
        """Return every identifier mentioned in ``annotation``."""
        return frozenset(
            {inner.id for inner in ast.walk(annotation) if isinstance(inner, ast.Name)}
            | {inner.attr for inner in ast.walk(annotation) if isinstance(inner, ast.Attribute)}
        )

    @staticmethod
    def introspects_signature(node: ast.AST) -> bool:
        """Whether ``node`` builds a second answer to a knot's declared inputs.

        The seam is ``Knot.input_json_schema``, which derives the declared inputs
        from ``process()``; reaching for ``signature`` / ``get_type_hints`` /
        ``get_annotations`` builds a rival that can disagree with it.

        Two acts are not that, and are excluded by what they do rather than by
        who does them (PIR-874):

        * introspecting ``__init__`` asks about *wiring*, which Rule 1 puts in the
          constructor and no input schema describes;
        * a class that publishes a ``__signature__`` is *constructing* the
          signature the seam later reads — a decorator turning a plain function
          into a knot's ``process`` — rather than deriving inputs from one.
        """
        if SourceShapes._publishes_signature(node):
            return False
        return any(
            isinstance(sub, ast.Call)
            and SourceShapes.call_name(sub) in SourceShapes._signature_calls
            and not SourceShapes._targets_constructor(sub)
            for sub in ast.walk(node)
        )

    @staticmethod
    def _targets_constructor(call: ast.Call) -> bool:
        """Whether ``call``'s first argument names ``__init__``."""
        if not call.args:
            return False
        target = call.args[0]
        return isinstance(target, ast.Attribute) and target.attr == "__init__"

    @staticmethod
    def _publishes_signature(node: ast.AST) -> bool:
        """Whether ``node`` assigns a ``__signature__``, i.e. builds one to be read."""
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Assign):
                continue
            for target in sub.targets:
                if isinstance(target, ast.Attribute) and target.attr == "__signature__":
                    return True
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.slice, ast.Constant)
                    and target.slice.value == "__signature__"
                ):
                    return True
        return False

    @staticmethod
    def imports_hashing(tree: ast.AST) -> frozenset[str]:
        """Return the content-hashing modules ``tree`` imports."""
        found: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(
                    alias.name.split(".")[0]
                    for alias in node.names
                    if alias.name.split(".")[0] in SourceShapes._hashing_modules
                )
            elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
                root = node.module.split(".")[0]
                if root in SourceShapes._hashing_modules:
                    found.add(root)
        return frozenset(found)

    # -- class surfaces --------------------------------------------------------

    @staticmethod
    def methods_of(node: ast.ClassDef) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
        """Return the methods defined directly in ``node``'s body, by name."""
        return {
            child.name: child
            for child in node.body
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
        }

    @staticmethod
    def _parameter_names(method: ast.FunctionDef | ast.AsyncFunctionDef) -> frozenset[str]:
        args = method.args
        return frozenset(arg.arg for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs)) - {
            "self",
            "cls",
        }

    @staticmethod
    def _own_attribute_subscript(expr: ast.expr) -> tuple[str, ast.expr] | None:
        """Return ``("_x", key)`` when ``expr`` is ``self._x[key]``, else ``None``."""
        if not isinstance(expr, ast.Subscript):
            return None
        base = expr.value
        if (
            isinstance(base, ast.Attribute)
            and isinstance(base.value, ast.Name)
            and base.value.id == "self"
        ):
            return base.attr, expr.slice
        return None

    @staticmethod
    def _own_attribute_call(call: ast.Call) -> tuple[str, str] | None:
        """Return ``("_x", "get")`` when ``call`` is ``self._x.get(...)``, else ``None``."""
        func = call.func
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Attribute)
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "self"
        ):
            return func.value.attr, func.attr
        return None

    @staticmethod
    def _is_runtime_key(key: ast.expr) -> bool:
        """Whether ``key`` is computed at run time rather than a literal or a slice."""
        return not isinstance(key, ast.Constant | ast.Slice)

    @staticmethod
    def keyed_store_attributes(node: ast.ClassDef) -> frozenset[str]:
        """Return the class's own attributes that carry a keyed put/get surface.

        See the module docstring: an attribute the class both *writes* under a
        run-time key (``self._x[key] = value``) and *reads back* under one
        (``self._x[key]``, ``self._x.get(key)``, ``self._x.pop(key)``,
        ``self._x.setdefault(key, ...)``) is a store of its own — whatever the
        methods around it are called.
        """
        written: set[str] = set()
        read: set[str] = set()
        for method in SourceShapes.methods_of(node).values():
            for sub in ast.walk(method):
                for target in SourceShapes._assignment_targets(sub):
                    found = SourceShapes._own_attribute_subscript(target)
                    if found is not None and SourceShapes._is_runtime_key(found[1]):
                        written.add(found[0])
                if isinstance(sub, ast.Subscript) and isinstance(sub.ctx, ast.Load):
                    found = SourceShapes._own_attribute_subscript(sub)
                    if found is not None and SourceShapes._is_runtime_key(found[1]):
                        read.add(found[0])
                if isinstance(sub, ast.Call):
                    accessor = SourceShapes._own_attribute_call(sub)
                    if (
                        accessor is not None
                        and accessor[1] in SourceShapes._keyed_readers
                        and sub.args
                        and SourceShapes._is_runtime_key(sub.args[0])
                    ):
                        read.add(accessor[0])
        return frozenset(written & read)

    @staticmethod
    def own_event_channels(node: ast.ClassDef) -> frozenset[str]:
        """Return the class's own attributes that are a private event channel.

        See the module docstring: an attribute a class *fills* with a callable
        handed to one of its methods and later *delivers* to, by calling the
        elements it holds, is a subscriber list of its own — a second event
        bus beside the run's emitters, whatever the two methods are called.
        """
        registered: set[str] = set()
        for method in SourceShapes.methods_of(node).values():
            handed = SourceShapes._parameter_names(method)
            for sub in ast.walk(method):
                if isinstance(sub, ast.Call):
                    accessor = SourceShapes._own_attribute_call(sub)
                    if (
                        accessor is not None
                        and accessor[1] in SourceShapes._collection_adders
                        and any(isinstance(arg, ast.Name) and arg.id in handed for arg in sub.args)
                    ):
                        registered.add(accessor[0])
                if isinstance(sub, ast.Assign) and isinstance(sub.value, ast.Name):
                    for target in sub.targets:
                        found = SourceShapes._own_attribute_subscript(target)
                        if found is not None and sub.value.id in handed:
                            registered.add(found[0])
        return frozenset(
            attribute for attribute in registered if SourceShapes._delivers_to(node, attribute)
        )

    @staticmethod
    def _delivers_to(node: ast.ClassDef, attribute: str) -> bool:
        """Whether the class calls the elements held in ``self.<attribute>``."""
        for method in SourceShapes.methods_of(node).values():
            for sub in ast.walk(method):
                if isinstance(sub, ast.Call):
                    found = SourceShapes._own_attribute_subscript(sub.func)
                    if found is not None and found[0] == attribute:
                        return True
                if isinstance(sub, ast.For | ast.AsyncFor) and SourceShapes._reads_attribute(
                    sub.iter, attribute
                ):
                    if SourceShapes._calls_any_of(sub, SourceShapes._bound_names(sub.target)):
                        return True
                if isinstance(sub, ast.ListComp | ast.SetComp | ast.GeneratorExp):
                    bound = frozenset(
                        name
                        for generator in sub.generators
                        for name in SourceShapes._bound_names(generator.target)
                    )
                    reads = any(
                        SourceShapes._reads_attribute(generator.iter, attribute)
                        for generator in sub.generators
                    )
                    if reads and SourceShapes._calls_any_of(sub.elt, bound):
                        return True
        return False

    @staticmethod
    def _calls_any_of(node: ast.AST, names: frozenset[str]) -> bool:
        return any(
            isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id in names
            for sub in ast.walk(node)
        )

    @staticmethod
    def _reads_attribute(expr: ast.AST, attribute: str) -> bool:
        return any(
            isinstance(sub, ast.Attribute)
            and sub.attr == attribute
            and isinstance(sub.value, ast.Name)
            and sub.value.id == "self"
            for sub in ast.walk(expr)
        )

    @staticmethod
    def _bound_names(target: ast.expr) -> frozenset[str]:
        return frozenset(sub.id for sub in ast.walk(target) if isinstance(sub, ast.Name))

    # -- engine seams ------------------------------------------------------------

    @staticmethod
    def steps_inner_run_by_hand(node: ast.ClassDef) -> bool:
        """Whether a method awaits core's inner-run seam from *inside* a loop.

        One engine round trip per item is the defect: the items' lineage becomes
        N unrelated runs and the iteration belongs to the class rather than to
        core's awaitable loop step.

        A loop that only *builds* the nodes of a single run is not this. That is
        the chain and fan-out shape knot-design-rules Rule 11 prescribes, and
        ``ParallelSpecialistFanOut`` documents: N siblings declared at build time
        and executed by one run. Every build-time topology is constructed by a
        loop, so firing on that would forbid the shape the rules require
        (PIR-874).
        """
        for method in SourceShapes.methods_of(node).values():
            loops = (
                sub
                for sub in ast.walk(method)
                if isinstance(sub, ast.For | ast.AsyncFor | ast.While)
            )
            for loop in loops:
                if any(
                    isinstance(inner, ast.Await)
                    and isinstance(inner.value, ast.Call)
                    and SourceShapes.self_method_called(inner.value) == SourceShapes._inner_run_seam
                    for inner in ast.walk(loop)
                ):
                    return True
        return False

    @staticmethod
    def returns_bare_verdict(method: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Whether ``method`` is annotated as returning a bare ``bool``."""
        returns = method.returns
        return isinstance(returns, ast.Name) and returns.id == "bool"

    # -- encapsulation ------------------------------------------------------------

    @staticmethod
    def foreign_private_writes(node: ast.AST, own_names: frozenset[str]) -> frozenset[str]:
        """Return the assignments ``node`` makes to another object's private attribute.

        See the module docstring: ``self``/``cls``/``super()``, a name in
        ``own_names`` (the enclosing class), and any local derived from
        ``self`` in the same scope are the object's own state; assigning a
        ``_private`` attribute on anything else configures another object by
        reaching past its surface.
        """
        found: set[str] = set()
        for scope in SourceShapes.scopes(node):
            derived = SourceShapes._self_derived_names(scope)
            for sub in SourceShapes.scoped_walk(scope):
                for target in SourceShapes._assignment_targets(sub):
                    if (
                        isinstance(target, ast.Attribute)
                        and target.attr.startswith("_")
                        and not target.attr.startswith("__")
                        and not SourceShapes._is_own_object(target.value, own_names | derived)
                    ):
                        found.add(ast.unparse(target))
        return frozenset(found)

    @staticmethod
    def _assignment_targets(node: ast.AST) -> list[ast.expr]:
        if isinstance(node, ast.Assign):
            return list(node.targets)
        if isinstance(node, ast.AugAssign | ast.AnnAssign):
            return [node.target]
        if isinstance(node, ast.Delete):
            return list(node.targets)
        return []

    @staticmethod
    def _self_derived_names(scope: ast.AST) -> frozenset[str]:
        """Return the locals in ``scope`` bound to an expression mentioning ``self``."""
        derived: set[str] = set()
        for sub in SourceShapes.scoped_walk(scope):
            if not isinstance(sub, ast.Assign) or not SourceShapes._mentions_self(sub.value):
                continue
            derived.update(target.id for target in sub.targets if isinstance(target, ast.Name))
        return frozenset(derived)

    @staticmethod
    def _mentions_self(expr: ast.AST) -> bool:
        return any(
            isinstance(sub, ast.Name) and sub.id in {"self", "cls"} for sub in ast.walk(expr)
        )

    @staticmethod
    def _is_own_object(value: ast.expr, own_names: frozenset[str]) -> bool:
        if isinstance(value, ast.Name):
            return value.id in {"self", "cls"} or value.id in own_names
        return SourceShapes._is_self(value)
