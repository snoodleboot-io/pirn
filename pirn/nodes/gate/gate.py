"""Gate — predicate-driven pass-through.

A ``Gate`` takes one parent and a predicate.  If the predicate returns
truthy, the gate's output is ``Ok(input_value)``; otherwise the gate
produces ``Skipped``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.gate._gate_closed import _GateClosedError


class Gate(Knot):
    """Pass-through if predicate is truthy; otherwise Skipped.

    A ``Gate`` takes exactly one parent knot and a predicate callable.  When the
    predicate returns truthy the gate's output is the input value unchanged;
    when it returns falsy the gate's output is ``Skipped``.  Downstream knots
    that depend on a ``Skipped`` result are also skipped, propagating the skip
    through the graph automatically.

    Algorithm:
        1. Resolution — the engine resolves the single parent knot and passes
           its output as the ``input`` argument to ``process()``.
        2. Predicate evaluation — ``process()`` calls ``predicate(input)``.
        3. Pass-through — if the predicate is truthy, ``input`` is returned
           unchanged and the engine wraps it in ``Ok``.
        4. Gate closure — if the predicate is falsy, ``_GateClosedError`` is
           raised inside ``process()``, which the engine would normally wrap as
           ``Err``.
        5. Skip conversion — ``Gate.__call__`` intercepts the ``Err`` result
           produced by step 4.  When the recorded exception type is
           ``_GateClosedError``, the error is converted to
           ``Skipped(reason="gate_closed")`` before being returned to the engine.
    """

    def __init__(
        self,
        *,
        input: Knot,
        predicate: Callable[[Any], bool],
        _config: KnotConfig | None = None,
        tapestry: Any = None,
    ) -> None:
        if not isinstance(input, Knot):
            raise TypeError("Gate: 'input' must be a Knot")
        if not callable(predicate):
            raise TypeError("Gate: 'predicate' must be callable")
        if _config is None:
            raise TypeError("Gate requires _config=KnotConfig(id=...)")

        self._mutable_predicate = predicate

        self._mutable_config = _config
        self._mutable_parents = {"input": input}
        self._mutable_config_values = {}
        self._mutable_input_adapters = {}
        self._mutable_output_adapter = None
        self._mutable_mapped_inputs: dict = {}

        from pirn.tapestry import _current_tapestry

        target = tapestry or _current_tapestry.get(None)
        if target is not None:
            target.register(self)

        self._frozen = True

    async def process(self, input: Any, **_: Any) -> Any:  # type: ignore[override]
        """Pass the input through if the predicate is truthy, or raise to signal gate closure.

        Args:
            input: Value produced by the upstream knot, evaluated by the predicate.

        Returns:
            The input value unchanged when the predicate returns truthy.

        Raises:
            _GateClosedError: If the predicate returns falsy; converted to Skipped by ``__call__``.
        """
        if self._mutable_predicate(input):
            return input
        raise _GateClosedError

    async def __call__(self, parent_results: Any) -> Any:
        from pirn.core.err import Err as _Err
        from pirn.core.skipped import Skipped as _Skipped

        result = await super().__call__(parent_results)
        if isinstance(result, _Err) and result.record.exc_type == "_GateClosedError":
            return _Skipped(reason="gate_closed")
        return result
