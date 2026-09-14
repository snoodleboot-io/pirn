# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style
"""``SpecialistHandle`` — a delegated specialist, invoked through ``__call__``, never ``process()``.

Four multi-agent pipelines delegate to specialists that are themselves
``SubTapestry`` instances. Each of them used to ``await specialist.process(...)``
directly. That is not the contract: ``process()`` *builds and returns the sink
knot* of the specialist's inner pipeline — it does not run it. Only
``__call__`` establishes the inner tapestry, runs the graph and extracts the
sink's output.

Calling ``process()`` therefore handed the caller a ``Knot`` where an answer was
expected. Because every one of those callers guarded with
``isinstance(raw, AgentResponse)``, the ``Knot`` failed the guard and was either
stringified into the answer or silently dropped — with the run still reporting
success. See PIR-769.

A handle is also how a specialist reaches a knot that invokes it
(:class:`~pirn_agents.specializations.multi_agent.specialist_invocation.SpecialistInvocation`,
:class:`~pirn_agents.specializations.multi_agent.reviewer_invocation.ReviewerInvocation`).
A ``SubTapestry`` passed to a knot constructor directly would be partitioned
into the knot's *parents* and resolved as an input — but the specialist is an
opaque callee the knot runs with its own inputs, not an upstream value. The
handle is a non-``Knot`` :class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue`,
so it is an ordinary declared input that reaches ``process()`` like any other
(knot-design-rules.md Rules 1 and 4 — no instance state).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, TypeGuard

from pirn.core.ok import Ok
from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.core.skipped import Skipped
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.specializations.multi_agent.specialist_invocation_error import (
    SpecialistInvocationError,
)


@dataclass(frozen=True, eq=False)
class SpecialistHandle(PirnOpaqueValue):
    """An opaque reference to one specialist pipeline, run to completion on :meth:`run`.

    Attributes
    ----------
    specialist:
        The specialist ``SubTapestry`` to delegate to.
    """

    specialist: SubTapestry

    def __post_init__(self) -> None:
        if not isinstance(self.specialist, SubTapestry):
            raise TypeError(
                f"SpecialistHandle: specialist must be a SubTapestry, "
                f"got {type(self.specialist).__name__}"
            )

    @staticmethod
    def by_name(specialists: object, *, owner: str) -> dict[str, SubTapestry]:
        """Validate a ``{name: specialist}`` registry and return it as a typed dict.

        Args:
            specialists: The runtime-bound registry a multi-agent pipeline received.
            owner: The pipeline's class name, prefixed to every error message.

        Returns:
            The registry, in its original order.

        Raises:
            ValueError: If ``specialists`` is not a mapping or is empty.
            TypeError: If a name is not a string or a specialist is not a ``SubTapestry``.
        """
        if not SpecialistHandle._is_mapping(specialists) or not specialists:
            raise ValueError(f"{owner}: specialists must be a non-empty mapping")
        registry: dict[str, SubTapestry] = {}
        for name, specialist in specialists.items():
            if not isinstance(name, str):
                raise TypeError(
                    f"{owner}: specialist names must be strings, got {type(name).__name__}"
                )
            if not isinstance(specialist, SubTapestry):
                raise TypeError(
                    f"{owner}: specialist {name!r} must be a SubTapestry, "
                    f"got {type(specialist).__name__}"
                )
            registry[name] = specialist
        return registry

    @staticmethod
    def _is_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
        """Narrow a runtime-bound registry to a mapping."""
        return isinstance(value, Mapping)

    async def run(self, **inputs: Any) -> Any:
        """Run the specialist to completion and return the value it produced.

        Args:
            **inputs: Inputs to supply to the specialist, overriding the values
                it was constructed with. These reach ``process()`` as keyword
                arguments, exactly as the engine would supply parent results.

        Returns:
            The specialist's output — the value its sink knot produced.

        Raises:
            SpecialistInvocationError: If the specialist failed or was skipped.
                Neither outcome carries a value, so there is nothing to return
                and the caller must not proceed as though there were.
        """
        specialist = self.specialist
        result = await specialist(inputs)
        if isinstance(result, Ok):
            return result.value
        if isinstance(result, Skipped):
            raise SpecialistInvocationError(specialist.knot_id, f"skipped ({result.reason})")
        raise SpecialistInvocationError(
            specialist.knot_id,
            f"{result.record.exc_type}: {result.record.message}",
        )
