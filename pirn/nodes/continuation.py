"""Continuation — attach dynamic next-step logic to any knot.

A continuation is a plain function that receives a knot's output and returns
a list of ``Next`` descriptors — one per successor to spawn.  The continuation
always returns at least one entry; use ``Next("end")`` to explicitly terminate
the flow.

Example::

    from pirn.nodes.continuation import Next, continues

    pool = {
        "summarise": SummariseKnot,
        "web_search": WebSearchKnot,
    }

    def router(result: SearchResult) -> list[Next]:
        if result.confidence < 0.6:
            return [Next("web_search", {"query": result.original_query})]
        return [Next("summarise", {"text": result.content})]

    search = WebSearchKnot(query=q, _config=KnotConfig(id="search"))
    continues(search, fn=router, pool=pool)

The continuation runs after ``search`` completes, calls ``router`` with the
result, and registers whatever it returns into the running extensible tapestry.
``WebSearchKnot`` itself has no knowledge of what comes after it.

For agentic flows the agent knot handles continuation logic itself — it runs,
inspects its output, and calls ``get_current_store().register(...)`` directly.
``continues()`` is for adding deterministic or rule-based next-steps to
individual knots without modifying them.

Both patterns can coexist: an agent spawns a search knot wrapped with
``continues()``; the search knot's fixed continuation runs, and its result
feeds back into the agent's own dynamic planning.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import get_current_store

# ── Types ─────────────────────────────────────────────────────────────────────

Pool = dict[str, type[Knot]]
ContinuationFn = Callable[[Any], "list[Next]"]


# ── Next ──────────────────────────────────────────────────────────────────────


@dataclass
class Next:
    """One successor to spawn from a continuation.

    ``action`` maps to a knot class in the pool.  ``inputs`` are passed as
    constructor kwargs — plain values become config constants, ``Knot``
    instances become parent edges exactly as in any pirn constructor.

    ``id`` overrides the auto-generated knot id.  Leave it ``None`` to get
    a stable derived id (``"{continuation_id}_{action}_{index}"``).
    """

    action: str
    inputs: dict[str, Any] = field(default_factory=dict)
    id: str | None = None


# ── Built-in terminal ─────────────────────────────────────────────────────────


class _EndKnot(Knot):
    """Terminal knot — registered when a continuation returns Next('end').

    Produces no output.  Its presence in the graph makes explicit that the
    flow terminated intentionally at this point, not due to an error or
    missing logic.
    """

    async def process(self, **_: Any) -> None:
        """Receive any inputs and return None to mark explicit flow termination.

        Returns:
            None, signalling that this branch of the flow has terminated intentionally.
        """
        return None


# ── WithContinuation ──────────────────────────────────────────────────────────


class WithContinuation(Knot):
    """Runs after a wrapped knot, calls a continuation, and spawns successors.

    The wrapped knot's output arrives as ``result``.  The continuation
    function is called with that value and must return a non-empty
    ``list[Next]``.  Each entry is looked up in the pool, constructed with
    the provided inputs, and registered into the running extensible tapestry.

    The continuation always creates at least one successor — termination is
    explicit via ``Next("end")``, which registers a built-in ``_EndKnot``.
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
        super().__init__(result=result, **kwargs)
        object.__setattr__(self, "_mutable_fn", fn)
        # Built-in end action is always available; user pool entries take
        # precedence if they supply their own "end" knot.
        object.__setattr__(self, "_mutable_pool", {WithContinuation._end: _EndKnot, **pool})

    async def process(self, result: Any, **_: Any) -> Any:  # type: ignore[override]
        """Invoke the continuation function on the upstream result, register successor knots, and return the result.

        Args:
            result: Output value of the wrapped upstream knot, passed unchanged to the continuation function.

        Returns:
            The upstream result value, forwarded unmodified after successor registration.

        Raises:
            KeyError: If a continuation-returned action name is not present in the pool.
        """
        fn: ContinuationFn = object.__getattribute__(self, "_mutable_fn")
        pool: Pool = object.__getattribute__(self, "_mutable_pool")

        nexts = fn(result)

        assert nexts, (
            f"{type(self).__name__}({self.knot_id!r}): continuation returned an "
            "empty list — the flow has no defined successor.  Return at least "
            "Next('end') to terminate explicitly."
        )

        store = get_current_store()
        if store is not None:
            for i, nxt in enumerate(nexts):
                if nxt.action not in pool:
                    raise KeyError(
                        f"{type(self).__name__}({self.knot_id!r}): action "
                        f"{nxt.action!r} not found in pool "
                        f"(available: {sorted(pool)})"
                    )
                knot_cls = pool[nxt.action]
                knot_id = (
                    nxt.id
                    if nxt.id is not None
                    else f"{self.knot_id}__{nxt.action}_{i}_{uuid.uuid4().hex[:6]}"
                )
                spawned = knot_cls(**nxt.inputs, _config=KnotConfig(id=knot_id))
                store.register(spawned)

        return result


# ── continues() ───────────────────────────────────────────────────────────────


def continues(
    knot: Knot,
    *,
    fn: ContinuationFn,
    pool: Pool,
) -> WithContinuation:
    """Attach a continuation to *knot*.

    Returns a ``WithContinuation`` node wired to run immediately after *knot*
    completes.  The continuation id is ``"{knot.knot_id}$cont"``.

    Must be used inside an extensible tapestry run.  In a non-extensible run
    the continuation fires but spawned knots are silently dropped (the store
    is not available).

    Args:
        knot:  The knot whose output drives the continuation.
        fn:    Continuation function ``(output) -> list[Next]``.  Must always
               return a non-empty list.
        pool:  Mapping of action name → knot class.  ``"end"`` is built-in.
    """
    return WithContinuation(
        result=knot,
        fn=fn,
        pool=pool,
        _config=KnotConfig(id=f"{knot.knot_id}__cont"),
    )
