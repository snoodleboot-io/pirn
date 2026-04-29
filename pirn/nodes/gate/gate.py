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
from pirn.nodes.gate._gate_closed import _GateClosed


class Gate(Knot):
    """Pass-through if predicate is truthy; otherwise Skipped."""

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

        from pirn.tapestry import _CURRENT_TAPESTRY

        target = tapestry or _CURRENT_TAPESTRY.get(None)
        if target is not None:
            target.register(self)

        self._frozen = True

    async def process(self, input: Any, **_: Any) -> Any:
        if self._mutable_predicate(input):
            return input
        raise _GateClosed

    async def __call__(self, parent_results: Any) -> Any:
        from pirn.core.err import Err as _Err
        from pirn.core.skipped import Skipped as _Skipped

        result = await super().__call__(parent_results)
        if isinstance(result, _Err) and result.record.exc_type == "_GateClosed":
            return _Skipped(reason="gate_closed")
        return result
