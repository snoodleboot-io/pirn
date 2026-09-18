"""``WithContinuation`` — attach dynamic next-step logic to any knot.

A continuation is a plain function that receives a knot's output and returns
a list of ``Next`` descriptors — one per successor to spawn.  The continuation
always returns at least one entry; use ``Next("end")`` to explicitly terminate
the flow.

Example::

    from pirn.nodes.with_continuation import WithContinuation
    from pirn.nodes.next import Next

    pool = {
        "summarise": SummariseKnot,
        "web_search": WebSearchKnot,
    }

    def router(result: SearchResult) -> list[Next]:
        if result.confidence < 0.6:
            return [Next("web_search", {"query": result.original_query})]
        return [Next("summarise", {"text": result.content})]

    search = WebSearchKnot(query=q, _config=KnotConfig(id="search"))
    WithContinuation.attach(search, fn=router, pool=pool)

The continuation runs after ``search`` completes, calls ``router`` with the
result, and registers whatever it returns into the running extensible tapestry.
``WebSearchKnot`` itself has no knowledge of what comes after it.

For agentic flows the agent knot handles continuation logic itself — it runs,
inspects its output, and calls ``Tapestry.current_store().register(...)`` directly.
``WithContinuation.attach()`` is for adding deterministic or rule-based next-steps to
individual knots without modifying them.

Both patterns can coexist: an agent spawns a search knot wrapped with
``WithContinuation.attach()``; the search knot's fixed continuation runs, and its result
feeds back into the agent's own dynamic planning.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.exceptions.extensible_run_required_error import ExtensibleRunRequiredError
from pirn.nodes.end_knot import EndKnot
from pirn.nodes.next import Next
from pirn.tapestry import Tapestry

# ── Types ─────────────────────────────────────────────────────────────────────

#: Action name -> anything that constructs the successor knot for that action.
#: A ``Knot`` subclass and a ``@KnotFactory.knot`` factory are both valid and
#: both used in tree; the contract the spawn site relies on is exactly "call it
#: with the ``Next``'s inputs and a ``_config`` and get a knot back", which is
#: also what ``validate_io`` can actually check.
Pool = dict[str, Callable[..., Knot]]
ContinuationFn = Callable[[Any], "list[Next]"]


# ── WithContinuation ──────────────────────────────────────────────────────────


class WithContinuation(Knot):
    """Runs after a wrapped knot, calls a continuation, and spawns successors.

    The wrapped knot's output arrives as ``result``.  The continuation
    function is called with that value and must return a non-empty
    ``list[Next]``.  Each entry is looked up in the pool, constructed with
    the provided inputs, and registered into the running extensible tapestry.

    The continuation always creates at least one successor — termination is
    explicit via ``Next("end")``, which registers a built-in ``EndKnot``.

    Algorithm:
        1. Resolution — the engine resolves the wrapped knot and passes its
           output as ``result`` to ``process()``.
        2. Invocation — ``process()`` calls the continuation function
           ``fn(result)``, which returns a ``list[Next]`` describing every
           successor to spawn.
        3. Non-empty guard — an empty return list is a caller error (there is
           no defined successor); it raises ``ValueError``, since a forgotten
           ``Next("end")`` must not read as "everything finished".  A bare
           ``assert`` used to stand here, which vanishes under ``python -O``
           and let the empty list through as a silent success.
        4. Store availability — if no extensible store is active (a
           non-extensible run, or a stray call outside a run), this raises
           ``ExtensibleRunRequiredError``.  It used to return ``result``
           unchanged, so the continuation ran and every successor it asked for
           was dropped with no trace, and a pipeline reported success having
           executed a prefix of itself.
        5. Pool lookup — for each ``Next`` entry, its ``action`` name is
           looked up in the pool (the built-in ``"end"`` action always maps to
           ``EndKnot`` unless the caller's pool overrides it). An unknown
           action raises ``KeyError`` naming the available actions.
        6. Spawn — the resolved knot class is constructed with ``nxt.inputs``
           as constructor kwargs and a derived or caller-supplied id, then
           registered with the running store so the engine picks it up
           mid-run.  A derived id is ``{continuation_id}_{action}_{index}``:
           stable, so a recorded run replays to the same knot ids.  It used to
           carry six hex digits of ``uuid4``, which made every spawned knot id
           different on every run and the whole spawned tail unreplayable.
        7. Pass-through — ``process()`` returns ``result`` unchanged; spawning
           successors is a side effect, not a transformation of the value.
    """

    # Built-in action name — always available without registering in a pool.
    _end: ClassVar[str] = "end"

    def __init__(
        self,
        result: Knot,
        *,
        fn: ContinuationFn,
        pool: Pool,
        **kwargs: Any,
    ) -> None:
        # ``fn`` and ``pool`` are declared on ``process()``, so they are wired
        # as this knot's inputs rather than stashed on ``_mutable_`` slots:
        # ``process()`` can then be called standalone with plain values (Rule 2)
        # and both are validated against their declared types (PIR-873).  The
        # built-in end action is always available; a user pool entry named
        # "end" takes precedence.
        super().__init__(
            result=result, fn=fn, pool={WithContinuation._end: EndKnot, **pool}, **kwargs
        )

    async def process(self, result: Any, fn: ContinuationFn, pool: Pool, **_: Any) -> Any:
        """Invoke the continuation function on the upstream result, register successor knots, and return the result.

        Args:
            result: Output value of the wrapped upstream knot, passed unchanged to the continuation function.
            fn: The continuation, ``(output) -> list[Next]``.
            pool: Action name -> knot class, including the built-in ``"end"``.

        Returns:
            The upstream result value, forwarded unmodified after successor registration.

        Raises:
            ValueError: If the continuation returned an empty list.
            ExtensibleRunRequiredError: If no extensible run is active, so the
                successors would have nowhere to go.
            KeyError: If a continuation-returned action name is not present in the pool.
        """
        nexts = fn(result)
        if not nexts:
            raise ValueError(
                f"{type(self).__name__}({self.knot_id!r}): continuation returned an "
                "empty list — the flow has no defined successor.  Return at least "
                "Next('end') to terminate explicitly."
            )

        store = Tapestry.current_store()
        if store is None:
            raise ExtensibleRunRequiredError(knot_class=type(self).__name__, knot_id=self.knot_id)

        for index, nxt in enumerate(nexts):
            if nxt.action not in pool:
                raise KeyError(
                    f"{type(self).__name__}({self.knot_id!r}): action "
                    f"{nxt.action!r} not found in pool "
                    f"(available: {sorted(pool)})"
                )
            knot_cls = pool[nxt.action]
            knot_id = nxt.id if nxt.id is not None else f"{self.knot_id}_{nxt.action}_{index}"
            spawned = knot_cls(**nxt.inputs, _config=KnotConfig(id=knot_id))
            store.register(spawned)

        return result

    @staticmethod
    def attach(
        knot: Knot,
        *,
        fn: ContinuationFn,
        pool: Pool,
    ) -> WithContinuation:
        """Attach a continuation to *knot*.

        Returns a ``WithContinuation`` node wired to run immediately after
        *knot* completes.  The continuation id is ``"{knot.knot_id}__cont"``.

        Must be used inside an extensible tapestry run.  In a non-extensible
        run the continuation raises ``ExtensibleRunRequiredError`` rather than
        dropping the successors it asked for.

        Args:
            knot:  The knot whose output drives the continuation.
            fn:    Continuation function ``(output) -> list[Next]``.  Must
                   always return a non-empty list.
            pool:  Mapping of action name → knot class.  ``"end"`` is built-in.
        """
        return WithContinuation(
            result=knot,
            fn=fn,
            pool=pool,
            _config=KnotConfig(id=f"{knot.knot_id}__cont"),
        )
