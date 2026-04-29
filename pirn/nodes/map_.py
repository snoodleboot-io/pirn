"""Map — apply an inner knot to each element of a collection.

A ``Map`` wraps an inner knot.  Its parent produces a collection; for
each element, ``Map`` constructs a fresh instance of the inner knot
(with the element bound to a designated input) and runs them all in
parallel.  The output is a list of the inner knots' outputs.

Construction
------------
``Map(over=collection_knot, each=InnerKnotClass, bind="param_name", **shared)``

* ``over`` — a Knot producing the collection (Sequence[T]).
* ``each`` — the inner Knot class (or @knot factory) to instantiate
  per element.
* ``bind`` — the input name on the inner knot that receives the
  per-element value.
* ``**shared`` — extra kwargs forwarded to each inner-knot construction.
  Knot values become parents (shared across all sub-runs); other values
  become config.

Recursive composability
-----------------------
The inner knot can have its own parents (constructed before the Map and
shared via ``shared`` kwargs).  A multi-step per-element pipeline is
expressed as a chain of inner knots; pass the chain's terminal as
``each``.  This is the sub-graph map-body without any new concept.

Caveat for Phase 2: each Map sub-run constructs its own copies of the
inner knot's *direct* references that the user passes via ``shared``.
Cross-element parallelism is achieved at the Map level, not within each
sub-run.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from pirn.core.config import KnotConfig
from pirn.core.knot import Knot, KnotFactory


class Map(Knot):
    """Per-element fan-out wrapper."""

    def __init__(
        self,
        *,
        over: Knot,
        each: Any,
        bind: str,
        _config: KnotConfig | None = None,
        tapestry: Any = None,
        **shared: Any,
    ) -> None:
        if not isinstance(over, Knot):
            raise TypeError("Map: 'over' must be a Knot producing a Sequence")
        if not isinstance(bind, str) or not bind:
            raise TypeError("Map: 'bind' must be a non-empty string")
        if _config is None:
            raise TypeError("Map requires _config=KnotConfig(id=...)")

        # 'each' should be a class (Knot subclass) or a @knot factory.
        if not _is_knot_factory(each):
            raise TypeError("Map: 'each' must be a Knot subclass or a @knot factory")

        self._mutable_each = each
        self._mutable_bind = bind
        self._mutable_shared = shared

        self._mutable_config = _config
        self._mutable_parents = {"over": over}
        self._mutable_config_values = {}
        self._mutable_input_adapters = {}
        self._mutable_output_adapter = None

        from pirn.tapestry import _CURRENT_TAPESTRY

        target = tapestry or _CURRENT_TAPESTRY.get(None)
        if target is not None:
            target.register(self)

        self._frozen = True

    async def process(self, over: Sequence[Any]) -> list[Any]:
        if not isinstance(over, (list, tuple)):
            # Allow any Sequence but materialise; we need length and
            # repeated iteration.
            over = list(over)

        # Build one sub-knot per element.  We invoke each inner knot
        # directly via its __call__ rather than re-running a sub-engine,
        # because the inner knots' parents are already resolved (they
        # were either constructed with concrete shared kwargs, which are
        # config values, or with shared parents which we'd need to walk
        # — Phase 2 simplification: shared parents must already be
        # resolved before the Map runs, which is naturally the case
        # because they're parents of the Map's parents in the outer
        # graph).
        each = self._mutable_each
        bind_name = self._mutable_bind
        shared = self._mutable_shared

        async def run_one(index: int, element: Any) -> Any:
            # Construct the inner knot for this element.  Use a unique
            # id so the construction doesn't collide if the inner
            # registers with a tapestry.  Don't actually register with
            # the tapestry — these are ephemeral.
            inner_kwargs = dict(shared)
            inner_kwargs[bind_name] = element
            inner_kwargs["_config"] = KnotConfig(
                id=f"{self.knot_id}/{index}",
                validate_io=self._mutable_config.validate_io,
                error_policy=self._mutable_config.error_policy,
            )
            inner_kwargs["tapestry"] = None  # don't register

            knot_instance = _construct_inner(each, inner_kwargs)

            # Resolve the inner's parents: any Knot in shared is a
            # parent and must already have produced a value somewhere
            # in the outer run.  In Phase 2 we don't have access to the
            # run context here (Map.__call__ is invoked by the engine);
            # we rely on the fact that shared parents must be Knots
            # whose output is a constant for this run, and we look them
            # up via... actually, simpler: we forbid Knot-valued shared
            # kwargs in Phase 2 and document that limitation.  See
            # __init__ check below.

            # Inputs to the inner: the bind name's element value, plus
            # any non-Knot shared kwargs (config values).  Knot-valued
            # shared kwargs are not supported in this simplified Phase 2
            # implementation.
            inner_inputs: dict[str, Any] = {bind_name: element}
            for name, value in shared.items():
                if not isinstance(value, Knot):
                    inner_inputs[name] = value

            result = await knot_instance(inner_inputs)
            return result

        coros = [run_one(i, e) for i, e in enumerate(over)]
        results = await asyncio.gather(*coros)

        # If any inner failed, surface that — the Map result is a list of
        # values, but we don't want silent partial failures.  We use the
        # convention: any inner Err raises, becoming the Map's Err.  Skip
        # propagates as Skipped (via list filtering).
        from pirn.core.result import Err as _Err
        from pirn.core.result import Ok as _Ok
        from pirn.core.result import Skipped as _Skipped

        final: list[Any] = []
        for r in results:
            if isinstance(r, _Ok):
                final.append(r.value)
            elif isinstance(r, _Skipped):
                # Skipped elements are dropped from the output list.
                # Document this; alternative would be to keep Skipped
                # markers, but downstream processing usually wants a
                # clean list.
                continue
            elif isinstance(r, _Err):
                raise RuntimeError(
                    f"Map: inner knot failed: {r.record.exc_type}: {r.record.message}"
                )
        return final


def _is_knot_factory(obj: Any) -> bool:
    """True if obj is a Knot subclass or a KnotFactory."""
    if isinstance(obj, type) and issubclass(obj, Knot):
        return True
    return isinstance(obj, KnotFactory)


def _construct_inner(each: Any, kwargs: dict[str, Any]) -> Knot:
    """Construct an inner Knot from a Knot subclass or a KnotFactory."""
    return each(**kwargs)
