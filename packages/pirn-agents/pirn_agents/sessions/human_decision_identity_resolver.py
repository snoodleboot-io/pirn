"""``HumanDecisionIdentityResolver`` — record a resume run's actor as the decider."""

from __future__ import annotations

from pirn.core.identity.identity_resolver import IdentityResolver

from pirn_agents.sessions.human_decision import HumanDecision


class HumanDecisionIdentityResolver(IdentityResolver):
    """Resolves a run's actor to the human who made a :class:`HumanDecision`.

    Attach one to the ``Tapestry`` a resume run executes against (leaving
    ``RunRequest.actor`` unset, since an explicit ``actor`` always wins over
    any resolver) so the resumed ``RunResult`` — and therefore its
    ``RunHistory`` row — records who approved or rejected it, without every
    caller having to remember to set ``actor=`` by hand.
    """

    def __init__(self, decision: HumanDecision) -> None:
        """Bind the resolver to ``decision``.

        Raises:
            TypeError: If ``decision`` is not a ``HumanDecision``.
        """
        if not isinstance(decision, HumanDecision):
            raise TypeError(
                f"HumanDecisionIdentityResolver: decision must be a HumanDecision, "
                f"got {type(decision).__name__}"
            )
        self._decision = decision

    def resolve(self) -> str | None:
        """Return the deciding operator's id, or ``None`` if not recorded."""
        return self._decision.decided_by
