"""``AgentResult`` — shared ``Payload`` base for the specialization result types.

ADR agents-speaks-core WS6b established the ``Payload[Frame, Data]`` split
for agents' cross-boundary value types (``AgentResponse =
Payload[GenerationFrame, str]``, ``ConversationPayload =
Payload[ConversationFrame, tuple[AgentMessage, ...]]``). PIR-868 completes the
same rebase for the specialization pattern outcomes
(``EvaluatorOptimizerResult``, ``LatsResult``, ``OrchestratorWorkersResult``,
``WorkerTaskResult``, ``PlanReActResult``, ``PromptChainResult``,
``SimulationResult``, ``ReflexionResult``, ``ReWooResult``, ``FallbackResult``,
``SelfAskResult``): each is now ``Payload[<Frame>, D]``, where the frame
carries the run-level facts (iteration counts, scores, candidate ids,
attempted/skipped names, budgets) and ``D`` is the answer/content the
pipeline actually produced.

``AgentResult`` itself is a thin, non-abstract generic ``Payload`` subclass —
not a dataclass, declaring no fields of its own — kept importable so the
family still shares one substitutable abstraction (DIP/LSP): callers may
depend on ``AgentResult`` rather than each concrete, and
``isinstance(x, AgentResult)`` keeps working for every result in the family.
Each concrete overrides ``_pirn_audit_dict`` exactly as it did before the
rebase (previously overriding the raising base's hook; now overriding
``Payload``'s metadata-delegating one) to fold in its own ``data`` field(s).

``Payload`` does not define value equality (``AgentResponse`` and
``ConversationPayload`` do not either), so ``AgentResult`` adds a structural
``__eq__`` — same concrete type, equal ``metadata`` and equal ``data`` — so
existing equality-based tests and call sites on the result family keep
working unchanged. Frozen-dataclass equality is not restored generally
because ``AgentResponse``/``ConversationPayload`` were never restored either;
this narrows the divergence to exactly this family, where it was observed to
matter (``SimulationResult`` equality).

References:
    - :class:`pirn.core.payload.Payload`
    - :class:`pirn.core.pirn_opaque_value.PirnOpaqueValue`
"""

from __future__ import annotations

from typing import TypeVar

from pirn.core.payload import Payload
from pirn.core.pirn_opaque_value import PirnOpaqueValue

M = TypeVar("M", bound=PirnOpaqueValue)
D = TypeVar("D")


class AgentResult(Payload[M, D]):
    """Thin generic ``Payload`` base for the specialization result family.

    Declares no fields and no behaviour beyond structural equality; each
    concrete ``Payload[<Frame>, D]`` subclass supplies its own frame type,
    ``__init__`` (accepting the same flat, pre-ADR field names it always
    did), read-only properties for those field names, and
    :meth:`_pirn_audit_dict`.
    """

    def __eq__(self, other: object) -> bool:
        """Structural equality: same concrete type, equal metadata and data.

        ``Payload`` defines no ``__eq__`` (identity equality), which would
        break existing value-equality expectations on this family (e.g.
        ``SimulationResult``). Comparing ``_metadata``/``_data`` instead of
        dataclass fields keeps this correct across every concrete without
        each one needing to declare its own.
        """
        if not isinstance(other, type(self)) or type(other) is not type(self):
            return NotImplemented
        return self._metadata == other._metadata and self._data == other._data
