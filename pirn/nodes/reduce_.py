"""Reduce — fold a list (typically from a Map) into one value.

A ``Reduce`` takes one parent producing a list and a ``combine``
callable; it folds the list using ``combine``.  Two combine signatures
are supported:

* ``combine(items: list[T]) -> R`` — receives the whole list at once.
* ``combine(acc: R, item: T) -> R`` — pairwise reduction; an
  ``initial`` value must be supplied.

The form is selected by inspection: if ``combine`` accepts exactly one
parameter, it's the whole-list form; if exactly two, it's the pairwise
form.

Example, whole-list::

    summed = Reduce(of=numbers, combine=sum, _config=KnotConfig(id="sum"))

Example, pairwise::

    counted = Reduce(
        of=words,
        combine=lambda acc, w: {**acc, w: acc.get(w, 0) + 1},
        initial={},
        _config=KnotConfig(id="count"),
    )

Reduce is functionally a thin wrapper over an Aggregator/Knot, but the
class makes the Map → Reduce idiom legible.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class Reduce(Knot):
    """Fold a list parent into a single value.

    A ``Reduce`` takes one parent knot whose output is a list and a ``combine``
    callable.  Two calling conventions are supported and selected automatically
    by inspecting ``combine``'s required parameter count.

    Algorithm:
        1. Signature inspection — at construction time, ``inspect.signature`` is
           used to count required positional parameters in ``combine``.  One
           required parameter selects the whole-list form; two required
           parameters select the pairwise form.  Any other count raises
           ``TypeError``.
        2. Pairwise validation — if the pairwise form is selected and no
           ``initial`` value is given, ``TypeError`` is raised immediately.
        3. Resolution — the engine resolves the single ``of`` parent and passes
           its output as the ``of`` argument to ``process()``.
        4. Whole-list reduction — ``combine(of)`` is called once with the entire
           list and its return value is the output.
        5. Pairwise reduction — starting from ``initial``, ``combine(acc, item)``
           is called for each element in ``of`` in order, accumulating into
           ``acc``.  The final ``acc`` is the output.

    Math:
        Whole-list form: ``output = combine(items)``

        Pairwise form: ``output = combine(... combine(combine(initial, items[0]),
        items[1]) ..., items[n-1])``

        Equivalent to Python's ``functools.reduce(combine, items, initial)`` but
        without the dependency on ``functools``.
    """

    _unset: ClassVar[object] = object()

    def __init__(
        self,
        *,
        of: Knot,
        combine: Callable[..., Any],
        initial: Any = ...,
        _config: KnotConfig | None = None,
        tapestry: Any = None,
    ) -> None:
        if initial is ...:
            initial = Reduce._unset
        if not isinstance(of, Knot):
            raise TypeError("Reduce: 'of' must be a Knot producing a list")
        if not callable(combine):
            raise TypeError("Reduce: 'combine' must be callable")
        if _config is None:
            raise TypeError("Reduce requires _config=KnotConfig(id=...)")

        # Inspect combine to pick the form.  Count REQUIRED parameters
        # (those without defaults).  Builtins like ``sum`` have signature
        # ``(iterable, /, start=0)`` — total params 2, required 1 → whole.
        sig = inspect.signature(combine)
        required = [
            p
            for p in sig.parameters.values()
            if p.kind
            in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.POSITIONAL_ONLY,
            )
            and p.default is inspect.Parameter.empty
        ]
        n_required = len(required)
        if n_required == 1:
            self._mutable_form = "whole"
        elif n_required == 2:
            self._mutable_form = "pairwise"
            if initial is Reduce._unset:
                raise TypeError("Reduce: pairwise combine (2 required args) requires 'initial'")
        else:
            raise TypeError(f"Reduce: 'combine' must take 1 or 2 required args, got {n_required}")

        self._mutable_combine = combine
        self._mutable_initial = initial

        self._mutable_config = _config
        self._mutable_parents = {"of": of}
        self._mutable_config_values = {}
        self._mutable_input_adapters = {}
        self._mutable_output_adapter = None
        self._mutable_mapped_inputs: dict = {}

        from pirn.tapestry import _current_tapestry

        target = tapestry or _current_tapestry.get(None)
        if target is not None:
            target.register(self)

        self._frozen = True

    async def process(self, of: list[Any], **_: Any) -> Any:  # type: ignore[override]
        """Fold the input list into a single value using the configured combine callable.

        Args:
            of: List of items produced by the parent knot to reduce.

        Returns:
            Single value resulting from applying combine to the list, either whole-list or pairwise.
        """
        if self._mutable_form == "whole":
            return self._mutable_combine(of)
        # Pairwise.
        acc = self._mutable_initial
        combine = self._mutable_combine
        for item in of:
            acc = combine(acc, item)
        return acc
