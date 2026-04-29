"""Aggregator — N parents combined into one value.

An ``Aggregator`` takes any number of parent knots and combines their
outputs through a user-supplied ``combine`` callable.  Functionally it
is a regular Knot whose ``process`` simply applies ``combine`` to its
inputs; the dedicated class makes the intent explicit and gives a clean
seam for visualisation.

Example::

    def merge(a: dict, b: dict) -> dict:
        return {**a, **b}

    with Tapestry() as t:
        first_half = ...
        second_half = ...
        merged = Aggregator(
            combine=merge,
            a=first_half,
            b=second_half,
            _config=KnotConfig(id="merge"),
        )

The ``combine`` callable receives the parent outputs as keyword
arguments matching the parent kwarg names.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from pirn.core.config import KnotConfig
from pirn.core.knot import Knot


class Aggregator(Knot):
    """Combine N parent outputs via a user callable."""

    def __init__(
        self,
        *,
        combine: Callable[..., Any],
        _config: KnotConfig | None = None,
        tapestry: Any = None,
        **parents: Any,
    ) -> None:
        if not callable(combine):
            raise TypeError("Aggregator: combine must be callable")
        if not parents:
            raise TypeError("Aggregator requires at least one parent")
        for name, value in parents.items():
            if not isinstance(value, Knot):
                raise TypeError(
                    f"Aggregator: parent {name!r} must be a Knot, "
                    f"got {type(value).__name__}"
                )

        # Stash combine and the parent set on _mutable_ slots.  We bypass
        # the standard Knot kwargs introspection because Aggregator's
        # process() takes **kwargs — but we still want the parents to
        # show up as parents on the knot, so we wire them manually.
        self._mutable_combine = combine
        self._mutable_combine_is_async = asyncio.iscoroutinefunction(combine)

        # Build the bare _mutable_ state ourselves (mirroring Knot.__init__
        # post-validation) since we know parents are all Knots and there
        # are no config values.
        if _config is None:
            raise TypeError("Aggregator requires _config=KnotConfig(id=...)")
        self._mutable_config = _config
        self._mutable_parents = dict(parents)
        self._mutable_config_values = {}
        self._mutable_input_adapters = {}
        self._mutable_output_adapter = None

        from pirn.tapestry import _CURRENT_TAPESTRY

        target = tapestry or _CURRENT_TAPESTRY.get(None)
        if target is not None:
            target.register(self)

        self._frozen = True

    async def process(self, **inputs: Any) -> Any:
        combine = self._mutable_combine
        if self._mutable_combine_is_async:
            return await combine(**inputs)
        # Sync combine: run in-loop (it's expected to be lightweight; for
        # heavyweight work, dispatch the Aggregator through ThreadDispatcher).
        return combine(**inputs)
