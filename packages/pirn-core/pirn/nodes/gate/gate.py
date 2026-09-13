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
           through bare, so the engine records the gate as skipped.
        5. Lineage — ``Gate.__call__`` notes whether the gate opened as
           ``extra["predicate_passed"]``.
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
        _config: KnotConfig | None = None,
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
        if _config is None:
            raise TypeError("Gate requires _config=KnotConfig(id=...)")

        self._mutable_execution_extra: dict[str, Any] = {}

        parents: dict[str, Knot] = {"input": input}
        if check is not None:
            parents["check"] = check
        self._bootstrap(
            config=_config,
            parents=parents,
            config_values={"predicate": predicate} if predicate is not None else {},
            tapestry=tapestry,
        )

        self._frozen = True

    async def process(  # type: ignore[override]
        self,
        input: Any,
        predicate: Callable[[Any], bool] | None = None,
        check: bool | None = None,
        **_: Any,
    ) -> Any:
        """Pass the input through if the decision is open, else declare the skip.

        Args:
            input: Value produced by the upstream knot, evaluated by the predicate.
            predicate: Callable that decides whether the gate stays open, when
                the gate was built with one.
            check: The wired ``Check``'s verdict, when the gate was built with one.

        Returns:
            The input value unchanged when the decision is open, otherwise
            ``Skipped(reason="gate_closed")``.
        """
        opened = check if check is not None else bool(predicate(input) if predicate else False)
        if opened:
            return input
        return Skipped(reason="gate_closed")

    def lineage_extra(self) -> dict[str, Any]:
        return {**super().lineage_extra(), **self._mutable_execution_extra}

    async def __call__(self, parent_results: Any) -> Any:
        result = await super().__call__(parent_results)
        self._mutable_execution_extra = {"predicate_passed": not isinstance(result, Skipped)}
        return result
