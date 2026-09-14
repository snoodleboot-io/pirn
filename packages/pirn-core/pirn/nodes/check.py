"""``Check`` — the predicate half of a ``Gate``: a knot whose answer is ``True`` or ``False``.

A ``Gate`` decides whether a value continues down the graph.  Its decision can
be a plain callable over the gated value (``predicate=``), or it can be the
output of a knot in its own right (``check=``): a ``Check`` that reads any
number of parents, does whatever work the decision needs — an evaluation, a
policy lookup, a model call — and answers ``bool``.  Naming the role gives
that knot a home in core: the ``*Check`` knots that assess data and feed a
``Gate`` (``docs/contributing/knot-design-rules.md``, Rule 7) are ``Check``s,
and a ``Gate`` can take one directly instead of a joined value and a lambda
(ADR agents-speaks-core, WS0).

A ``Check`` is an ordinary knot in every other respect: it declares its
inputs on ``process()``, runs under the engine with lineage and a
``Result``, and can be wired anywhere a ``bool``-valued knot is useful.
Only its output contract is stricter.

Algorithm:
    1. ``process()`` computes the verdict from its declared inputs and
       returns it.
    2. ``__call__`` runs the standard ``Knot.__call__`` pipeline (input
       validation, ``process()``, output validation against the subclass's
       return hint).
    3. An ``Ok`` whose value is not a ``bool`` — whatever the return hint,
       and whether or not ``validate_io`` is on — becomes
       ``Err(TypeError)``: a ``Check`` never leaks a truthy stand-in for
       a verdict into a ``Gate``.
    4. ``Err`` and ``Skipped`` pass through unchanged.

Skip reason.  A ``Check`` may name why a ``False`` verdict stops the graph by
setting the class attribute ``skip_reason`` (``None`` by default).  A ``Gate``
closed by such a check records that reason in its own lineage row instead of
the generic ``"gate_closed"``, and every knot skipped because of the gate
records it too, instead of the engine's generic
``"parent_failed_or_skipped"`` — so a raw lineage row says *why* (PIR-872).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from pirn.core.err import Err
from pirn.core.knot import Knot
from pirn.core.ok import Ok
from pirn.core.result import Result
from pirn.managers.exception_record import ExceptionRecord


class Check(Knot):
    """A knot whose ``process()`` answers ``True`` or ``False``.

    Subclass and implement ``async def process(self, ..., **_: Any) -> bool``.
    Wire one into a ``Gate`` with ``Gate(input=value, check=verdict, ...)``.
    Set ``skip_reason`` to name the skip a ``False`` verdict causes.
    """

    #: The reason a ``Gate`` closed by this check records and propagates to
    #: every knot it skips, or ``None`` for the gate's generic, unpropagated
    #: ``"gate_closed"``.
    skip_reason: ClassVar[str | None] = None

    # ``process`` below is declared in the gradual parameter form; see
    # ``Knot._dynamic_process_signature`` for why (PIR-833).
    _dynamic_process_signature: ClassVar[bool] = True

    async def process(self, *args: Any, **_: Any) -> bool:
        """Compute the verdict.  Subclasses name their inputs and return ``bool``.

        Raises:
            NotImplementedError: Always; subclasses must override this method.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement process()")

    async def __call__(self, parent_results: Mapping[str, Any]) -> Result[Any]:
        """Run as any knot, then refuse a non-``bool`` verdict as ``Err``."""
        result = await super().__call__(parent_results)
        if isinstance(result, Ok) and not isinstance(result.value, bool):
            verdict = TypeError(
                f"{type(self).__name__}({self.knot_id!r}).process() must return a bool, "
                f"got {type(result.value).__name__}"
            )
            return Err(record=ExceptionRecord.for_knot(self.knot_id, verdict))
        return result
