"""``AgentResult`` — shared base for the specialization result value objects.

The DIP seam behind the ``*Result`` family. Every specialization pattern that
returns a typed outcome (``EvaluatorOptimizerResult``, ``LatsResult``,
``OrchestratorWorkersResult``, ``WorkerTaskResult``, ``PlanReActResult``,
``PromptChainResult``, ``SimulationResult``, ``ReflexionResult``,
``ReWooResult``, ``FallbackResult``, ``SelfAskResult``) is a
``@dataclass(frozen=True)`` wrapper over :class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue`
whose only shared surface is the :meth:`_pirn_audit_dict` override that emits the
flat, lineage-relevant dict pydantic serialises at knot boundaries. Consolidating
them onto one base lets callers depend on the abstraction ``AgentResult`` rather
than each concrete, and gives every concrete a single substitutable contract.

Following the house interface style (never :class:`typing.Protocol`), the base
is a plain :class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue` subclass whose
:meth:`_pirn_audit_dict` raises :class:`NotImplementedError`; each concrete
result overrides it — exactly as it previously overrode
``PirnOpaqueValue._pirn_audit_dict`` — so the rebase changes no observable
behavior. The base is intentionally *not* itself a dataclass: it declares no
fields, so a ``@dataclass(frozen=True)`` concrete inherits it exactly as it
inherited the non-dataclass ``PirnOpaqueValue`` (no field-order or default
drift, and frozen consistency is preserved because the base contributes no
dataclass fields).

References:
    - :class:`pirn.core.pirn_opaque_value.PirnOpaqueValue`
"""

from __future__ import annotations

from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class AgentResult(PirnOpaqueValue):
    """Abstract base for the frozen result value objects of the specializations.

    Concrete results are ``@dataclass(frozen=True)`` subclasses that declare
    their own fields and override :meth:`_pirn_audit_dict` to emit a flat dict of
    those fields. The base itself is never serialised directly; it exists so the
    result family shares one abstraction (DIP) and one substitutable contract
    (LSP): every concrete produces the primitive audit form pydantic emits at the
    knot boundary.
    """

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Return the primitive dict pydantic emits for this result.

        Concrete subclasses override this with a flat dict of their own fields.
        The base raises to signal it is abstract.

        Raises:
            NotImplementedError: Always, on the base class.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement _pirn_audit_dict()")
