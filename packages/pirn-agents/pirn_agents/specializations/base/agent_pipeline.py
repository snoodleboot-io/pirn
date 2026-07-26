"""``AgentPipeline`` — shared base for the specialization pipeline knots.

The DIP seam behind the specialization pattern family. Every agentic pattern in
``specializations/**`` whose execution body is a complete inner tapestry is a
:class:`~pirn.nodes.sub_tapestry.SubTapestry` subclass implementing
``process(**kwargs) -> Knot`` (the RAG pipelines, the structured-output
extractors, the multi-agent orchestrations, the specialized agents, the
guardrail gates, the ReAct/LATS/ReWOO/Reflexion loops, the document-processing
pipelines, the RAPTOR/parent-document ingestors, …). Consolidating them onto one
base lets callers depend on the abstraction ``AgentPipeline`` rather than each
concrete, and gives every concrete a single substitutable contract.

The family is defined by its base *primitive* (``SubTapestry``), not by a
filename suffix: every ``*_pipeline`` module is a member, and so are the gates,
agents, loops, searches, and ingestors that share the identical
``process -> Knot`` contract.

Following the house interface style (never :class:`typing.Protocol`), the base
is a :class:`~pirn.nodes.sub_tapestry.SubTapestry` subclass whose :meth:`process`
raises :class:`NotImplementedError` — mirroring ``SubTapestry.process`` itself
and the :class:`~pirn_agents.interfaces.router.Router` house pattern. Each
concrete overrides ``process`` with its own keyword signature, exactly as it
previously overrode ``SubTapestry.process``, so the MRO resolves to the concrete
and the inserted base stub is unreachable — the rebase changes no observable
behavior. The base declares no ``__init__``, so ``super().__init__`` still
reaches ``SubTapestry.__init__`` (which captures the outer history) with no
field or default drift.

References:
    - :class:`pirn.nodes.sub_tapestry.SubTapestry`
    - :class:`pirn_agents.interfaces.router.Router`
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.nodes.sub_tapestry import SubTapestry


class AgentPipeline(SubTapestry):
    """Abstract base for specialization knots whose body is an inner tapestry.

    Concrete pipelines subclass this and override :meth:`process` with their own
    keyword signature, building the inner pipeline and returning its terminal
    (sink) knot. The base itself is never placed in a graph directly; it exists
    so the pattern family shares one abstraction (DIP) and one substitutable
    contract (LSP): each ``process`` assembles an inner tapestry and returns the
    sink knot whose output becomes this knot's output.
    """

    async def process(self, **_: Any) -> Knot:
        """Declare the inner pipeline and return its terminal knot.

        Concrete subclasses override this with their own keyword parameters,
        build the inner pipeline (knots auto-register into the tapestry context
        the base establishes), and return the sink knot. The base raises to
        signal it is abstract.

        Raises:
            NotImplementedError: Always, on the base class.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement process()")
