"""Gate — predicate-driven pass-through.

A ``Gate`` takes one parent and a decision.  If the decision is open, the
gate's output is ``Ok(input_value)``; otherwise the gate produces
``Skipped``.  The decision is either a predicate callable over the input or
the ``bool`` output of a ``Check`` knot.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.ok import Ok
from pirn.core.skipped import Skipped
from pirn.nodes.check import Check


class Gate(Knot):
    """Pass-through if the decision is open; otherwise Skipped.

    A ``Gate`` takes exactly one ``input`` parent and one decision.  The
    decision is either ``predicate=``, a callable over the input value, or
    ``check=``, a ``Check`` knot whose ``bool`` output opens the gate; exactly
    one of the two must be given.  When the decision is open the gate's
    output is the input value unchanged; when it is closed the gate's output
    is ``Skipped``.  Downstream knots that depend on a ``Skipped`` result are
    also skipped, propagating the skip through the graph automatically.

    Why one input.  A gate's contract is "its input, unchanged": the output
    carries the input's identity (its content hash) so lineage shows the same
    value flowing through.  Accepting several inputs and emitting a mapping
    would make the gate synthesise a new value with its own hash and no
    upstream identity, and would put a join inside a filter.  Joining is
    ``Aggregator``'s job; and with ``check=`` the common case — gate value
    ``A`` on a verdict computed from ``A`` and ``B`` — needs no join at all:
    the ``Check`` reads both, the gate passes ``A``.  Wire a join first when
    the downstream really needs several values together.

    Algorithm:
        1. Resolution — the engine resolves the ``input`` parent (and the
           ``check`` parent, when one is wired) and passes them to
           ``process()``.
        2. Decision — ``process()`` reads the ``check`` verdict when there is
           one, else calls ``predicate(input)``.
        3. Pass-through — if the decision is open, ``input`` is returned
           unchanged and the engine wraps it in ``Ok``.
        4. Gate closure — otherwise ``process()`` returns
           ``Skipped(reason="gate_closed")``, which ``Knot.__call__`` passes
           through bare, so the engine records the gate as skipped.  When the
           ``check`` names a ``skip_reason`` (``Check.skip_reason``), the skip
           carries that reason instead and is marked ``propagates``, so every
           knot the closed gate skips records the same reason rather than the
           engine's generic ``"parent_failed_or_skipped"``.
        5. Lineage — ``Gate.__call__`` notes whether the gate opened as
           ``extra["predicate_passed"]``.  A gate whose decision *failed* --
           the predicate raised, or the verdict failed validation -- records
           no such key: it reached no verdict, and reporting ``True`` (as it
           once did) made a crashed predicate indistinguishable from one that
           opened the gate.
        6. A ``Check`` that failed or was skipped never reaches ``process()``:
           under the default error policy the gate itself is skipped, like
           any knot whose parent did not produce a value.
    """

    def __init__(
        self,
        *,
        input: Knot,
        predicate: Callable[[Any], bool] | None = None,
        check: Check | None = None,
        _config: KnotConfig,
        tapestry: Any = None,
    ) -> None:
        if not isinstance(input, Knot):
            raise TypeError("Gate: 'input' must be a Knot")
        if (predicate is None) == (check is None):
            raise TypeError("Gate: give exactly one of 'predicate' or 'check'")
        if predicate is not None and not callable(predicate):
            raise TypeError("Gate: 'predicate' must be callable")
        if check is not None and not isinstance(check, Check):
            raise TypeError("Gate: 'check' must be a Check knot")

        self._mutable_execution_extra: dict[str, Any] = {}

        # Every input is declared on ``process()``, so the standard constructor
        # wires them: ``check`` is a parent when a ``Check`` is given and the
        # constant ``None`` otherwise, and either way the verdict reaching
        # ``process()`` is validated against ``bool | None`` -- which a
        # hand-rolled ``_bootstrap`` built no adapter for at all (PIR-873).
        super().__init__(
            input=input,
            predicate=predicate,
            check=check,
            closed_reason=(
                type(check).skip_reason
                if check is not None and type(check).skip_reason is not None
                else None
            ),
            _config=_config,
            tapestry=tapestry,
        )

    async def process(
        self,
        input: Any,
        predicate: Callable[[Any], bool] | None = None,
        check: bool | None = None,
        closed_reason: str | None = None,
        **_: Any,
    ) -> Any:
        """Pass the input through if the decision is open, else declare the skip.

        Args:
            input: Value produced by the upstream knot, evaluated by the predicate.
            predicate: Callable that decides whether the gate stays open, when
                the gate was built with one.
            check: The wired ``Check``'s verdict, when the gate was built with one.
            closed_reason: The wired ``Check``'s ``skip_reason``, when it names one.

        Returns:
            The input value unchanged when the decision is open, otherwise
            ``Skipped(reason="gate_closed")`` — or, when the check names a
            reason, ``Skipped(reason=closed_reason, propagates=True)``.
        """
        opened = check if check is not None else bool(predicate(input) if predicate else False)
        if opened:
            return input
        if closed_reason is not None:
            return Skipped(reason=closed_reason, propagates=True)
        return Skipped(reason="gate_closed")

    def lineage_extra(self) -> dict[str, Any]:
        return {**super().lineage_extra(), **self._mutable_execution_extra}

    async def __call__(self, parent_results: Any) -> Any:
        """Run the gate and note whether it opened, for lineage.

        ``predicate_passed`` used to be ``not isinstance(result, Skipped)``,
        which recorded ``True`` for a gate whose predicate *raised*: an ``Err``
        is not a ``Skipped``, so a crashed predicate read in lineage exactly
        like one that returned ``True``.  The gate opened only when it produced
        a value, and a failed decision yields no verdict at all, so the key is
        absent rather than guessed (PIR-873).
        """
        result = await super().__call__(parent_results)
        if isinstance(result, Ok):
            self._mutable_execution_extra = {"predicate_passed": True}
        elif isinstance(result, Skipped):
            self._mutable_execution_extra = {"predicate_passed": False}
        else:
            self._mutable_execution_extra = {}
        return result
