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

import inspect
from collections.abc import Callable
from typing import Any, get_type_hints

from pydantic import TypeAdapter

from pirn.core.async_callable import AsyncCallable
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.exceptions.unresolved_annotation_error import UnresolvedAnnotationError


class Aggregator(Knot):
    """Combine N parent outputs via a user callable.

    An ``Aggregator`` waits for all declared parent knots to produce values,
    then invokes ``combine`` with those values as keyword arguments.  The
    return value of ``combine`` becomes the aggregator's output.

    Parents are wired positionally by kwarg name: the key used when passing
    the parent to ``Aggregator(...)`` is the key under which its resolved
    value is passed to ``combine``.

    Why the validation lives here rather than on ``process()``.  An
    ``Aggregator``'s parent names are chosen at construction, so its
    ``process(**inputs)`` has no signature to introspect and the standard
    ``Knot`` constructor has nothing to build adapters from.  ``combine``'s own
    signature is the contract instead: it is what actually receives the parent
    values, so its parameter hints are the input adapters and its return hint
    is the output adapter.  Without this an ``Aggregator`` was the one knot for
    which ``KnotConfig.validate_io`` did nothing at all, and a parent wired
    under a name ``combine`` does not accept only failed once the run reached
    it (PIR-873).

    Algorithm:
        1. Validation — all ``**parents`` kwargs must be ``Knot`` instances;
           ``combine`` must be callable; at least one parent must be given; and
           ``combine`` must accept every parent name (unless it takes
           ``**kwargs``).
        2. Adapters — ``combine``'s parameter and return hints become this
           knot's input and output adapters, so ``validate_io`` checks the
           values ``combine`` is handed and the value it returns.
        3. DAG registration — all parents are stored as graph edges; the engine
           schedules this knot only after all parents have completed.
        4. Resolution — the engine resolves every parent concurrently (the
           scheduler handles ordering) and passes their outputs as keyword
           arguments to ``process()``.
        5. Combine invocation — ``process()`` calls ``combine(**inputs)`` where
           each key is the parent kwarg name and each value is that parent's
           resolved output.  Both sync and async ``combine`` callables are
           supported; async callables are awaited directly.
        6. Output — the value returned by ``combine`` is returned from
           ``process()`` and wrapped in ``Ok`` by the engine.
    """

    def __init__(
        self,
        *,
        combine: Callable[..., Any],
        _config: KnotConfig,
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

        # Stash combine on a _mutable_ slot.  We bypass the standard Knot
        # kwargs introspection because Aggregator's process() takes
        # **kwargs — but we still want the parents to show up as parents on
        # the knot, so we wire them manually via _bootstrap.  ``combine``
        # cannot be declared as a process() parameter (Rule 2's usual fix)
        # because parent names are dynamic and could collide with it.
        self._mutable_combine = combine
        self._mutable_combine_is_async = AsyncCallable.is_async_callable(combine)

        Aggregator._reject_unaccepted_parents(combine, set(parents), _config)
        input_adapters, output_adapter = Aggregator._adapters_for(combine)
        self._bootstrap(
            config=_config,
            parents=dict(parents),
            input_adapters=input_adapters,
            output_adapter=output_adapter,
            tapestry=tapestry,
        )

        self._frozen = True

    @staticmethod
    def _reject_unaccepted_parents(
        combine: Callable[..., Any], names: set[str], config: KnotConfig
    ) -> None:
        """Refuse a parent name ``combine`` cannot receive.

        A parent wired under a name ``combine`` has no parameter for is a
        wiring mistake, and it used to surface only once the run reached the
        aggregator, as a ``TypeError`` from the call itself.

        Args:
            combine: The fold callable.
            names: The parent kwarg names wired at construction.
            config: This knot's framework config, for the error message.

        Raises:
            TypeError: If ``combine`` accepts no ``**kwargs`` and some parent
                name is not one of its parameters.
        """
        try:
            signature = inspect.signature(combine)
        except (TypeError, ValueError):  # a builtin or C callable has no signature
            return
        if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values()):
            return
        accepted = {
            name
            for name, param in signature.parameters.items()
            if param.kind
            in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        }
        unaccepted = sorted(names - accepted)
        if unaccepted:
            raise TypeError(
                f"Aggregator({config.id!r}): combine does not accept parent(s) "
                f"{unaccepted!r}; its parameters are {sorted(accepted)!r}"
            )

    @staticmethod
    def _adapters_for(
        combine: Callable[..., Any],
    ) -> tuple[dict[str, TypeAdapter[Any]], TypeAdapter[Any] | None]:
        """Build this knot's input/output adapters from ``combine``'s hints.

        Args:
            combine: The fold callable whose signature is this knot's contract.

        Returns:
            ``(input adapters by parent name, output adapter or None)``.  A
            parameter or return with no hint gets no adapter, exactly as an
            unannotated ``process()`` parameter does.

        Raises:
            UnresolvedAnnotationError: If ``combine``'s hints cannot be
                resolved.  A declared type that resolves to nothing cannot be
                validated, and silently dropping it is what made
                ``validate_io`` a no-op in the first place.
        """
        try:
            hints = get_type_hints(combine, include_extras=True)
        except TypeError:
            # Not a hint-able object at all (a C builtin, a callable instance
            # with no ``__annotations__``): it declares no contract, so there is
            # nothing to validate -- the same outcome as an unannotated
            # ``process()`` parameter.
            return {}, None
        except Exception as exc:
            raise UnresolvedAnnotationError(knot_class="Aggregator", cause=exc) from exc
        returns = hints.pop("return", Any)
        return (
            {name: TypeAdapter(hint) for name, hint in hints.items() if hint is not Any},
            None if returns is Any else TypeAdapter(returns),
        )

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
