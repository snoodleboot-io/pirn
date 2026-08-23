"""``Router`` — shared interface for every routing knot.

The DIP seam behind the router family. A router inspects a request (a message,
task, score, or candidate set) and selects where it should go next — a branch, a
specialist, a tool, an escalation, or an ordered fallback chain. Across the
package this shape is implemented by ``specializations/routing/*``
(``IntentRouter``, ``CapabilityRouter``, ``CandidateRouter``,
``ConfidenceRouter``), plus ``OrchestratorRouter`` (multi-agent),
``CorrectiveRouter`` (RAG), ``EscalationRouter`` (human-in-the-loop), and
``ToolRouter`` (planning). Consolidating them onto one base lets callers depend
on the abstraction ``Router`` rather than each concrete, and gives every
concrete a single substitutable contract.

Following the house interface style (never :class:`typing.Protocol`), the base
is a :class:`~pirn.core.knot.Knot` whose :meth:`process` raises
:class:`NotImplementedError`; each concrete router overrides ``process`` with
its own keyword signature — exactly as it previously overrode ``Knot.process`` —
so the rebase changes no observable behavior.

Note:
    :class:`~pirn_agents.specializations.routing.model_cascade_router.ModelCascadeRouter`
    **is** a member of this family, as of PIR-718.

    It was previously excluded, and the exclusion was documented here as
    intentional. That reading was wrong: PIR-728, the story that wrote it, names
    the cascade router as one of the "9 routers, no ``Router`` base" and hands
    the shape question forward — "coordinate with WS7·S3/S6". The exclusion meant
    *not in that PR*, in a strictly behaviour-preserving story that could not
    afford to change a runtime surface. It was a deferral, not a decision, and
    PIR-718 discharges it.

    The port keeps the returned
    :class:`~pirn_agents.specializations.routing.cascade_outcome.CascadeOutcome`
    unchanged; only the constructor (now kwargs-only with ``_config``) and the
    entry point (``route`` → ``Knot.process``) moved.

References:
    - :class:`pirn.core.knot.Knot`
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot


class Router(Knot):
    """Abstract base for knots that route a request to a selected destination.

    Concrete routers subclass this and override :meth:`process` with their own
    keyword signature. The base itself is never placed in a graph directly; it
    exists so routers share one abstraction (DIP) and one substitutable contract
    (LSP): each ``process`` inspects a request and returns the chosen route,
    branch, or ordered candidate set.
    """

    # ``process`` below is declared in the gradual parameter form; see
    # ``Knot._dynamic_process_signature`` for why (PIR-833).
    _dynamic_process_signature: ClassVar[bool] = True

    async def process(self, *args: Any, **kwargs: Any) -> Any:
        """Select a destination for the given request.

        Concrete subclasses override this with their own keyword parameters and
        return type. The base raises to signal it is abstract.

        Raises:
            NotImplementedError: Always, on the base class.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement process()")
