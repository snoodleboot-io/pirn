"""Aggregator — N parents combined into one value.

An ``Aggregator`` takes any number of parent knots and combines their
outputs through a user-supplied ``combine`` callable.  Functionally it
is a regular Knot whose ``process`` simply applies ``combine`` to its
inputs; the dedicated class makes the intent explicit and gives a clean
seam for visualisation.

Example::

    def merge(left: dict, right: dict) -> dict:
        return {**left, **right}

    with Tapestry() as t:
        first_half = ...
        second_half = ...
        merged = Aggregator(
            combine=merge,
            left=first_half,
            right=second_half,
            _config=KnotConfig(id="merge"),
        )

The ``combine`` callable receives the parent outputs as keyword
arguments matching the parent kwarg names.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class Aggregator(Knot):
    """Combine N parent outputs via a user callable.

    An ``Aggregator`` waits for all declared parent knots to produce values,
    then invokes ``combine`` with those values as keyword arguments.  The
    return value of ``combine`` becomes the aggregator's output.

    Parents are wired positionally by kwarg name: the key used when passing
    the parent to ``Aggregator(...)`` is the key under which its resolved
    value is passed to ``combine``.

    Algorithm:
        1. Validation — all ``**parents`` kwargs must be ``Knot`` instances;
           ``combine`` must be callable; at least one parent must be given.
        2. DAG registration — all parents are stored as graph edges; the engine
           schedules this knot only after all parents have completed.
        3. Resolution — the engine resolves every parent concurrently (the
           scheduler handles ordering) and passes their outputs as keyword
           arguments to ``process()``.
        4. Combine invocation — ``process()`` calls ``combine(**inputs)`` where
           each key is the parent kwarg name and each value is that parent's
           resolved output.  Both sync and async ``combine`` callables are
           supported; async callables are awaited directly.
        5. Output — the value returned by ``combine`` is returned from
           ``process()`` and wrapped in ``Ok`` by the engine.
    """

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
                    f"Aggregator: parent {name!r} must be a Knot, got {type(value).__name__}"
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
        self._mutable_mapped_inputs: dict = {}

        from pirn.tapestry import _current_tapestry

        target = tapestry or _current_tapestry.get(None)
        if target is not None:
            target.register(self)

        self._frozen = True

    async def process(self, **inputs: Any) -> Any:
        """Combine all parent outputs by applying the combine callable to the resolved keyword arguments.

        Args:
            **inputs: Resolved outputs of each parent knot, keyed by the parent kwarg name.

        Returns:
            Value returned by the combine callable when invoked with the parent outputs.
        """
        combine = self._mutable_combine
        if self._mutable_combine_is_async:
            return await combine(**inputs)
        # Sync combine: run in-loop (it's expected to be lightweight; for
        # heavyweight work, dispatch the Aggregator through ThreadDispatcher).
        return combine(**inputs)
