"""Gate — predicate-driven pass-through.

A ``Gate`` takes one parent and a predicate.  If the predicate returns
truthy, the gate's output is ``Ok(input_value)``; otherwise the gate
produces ``Skipped``.

Useful for conditional execution: downstream knots wired to a gate run
only when the gate opens.

Example::

    with Tapestry() as t:
        config = ...
        only_if_enabled = Gate(
            input=config,
            predicate=lambda cfg: cfg.get("enabled", False),
            _config=KnotConfig(id="enabled?"),
        )
        # heavy_work runs only when config.enabled is true
        heavy_work(cfg=only_if_enabled, ...)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pirn.core.config import KnotConfig
from pirn.core.knot import Knot


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

    async def process(self, input: Any) -> Any:
        if self._mutable_predicate(input):
            return input
        raise _GateClosed

    async def __call__(self, parent_results: Any) -> Any:
        from pirn.core.result import Err as _Err
        from pirn.core.result import Skipped as _Skipped

        result = await super().__call__(parent_results)
        if isinstance(result, _Err) and result.record.exc_type == "_GateClosed":
            return _Skipped(reason="gate_closed")
        return result


class _GateClosed(Exception):
    """Internal sentinel; converted to Skipped by Gate.__call__."""
