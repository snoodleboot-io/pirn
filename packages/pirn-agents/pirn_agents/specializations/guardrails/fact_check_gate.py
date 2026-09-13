"""``FactCheckGate`` — deprecated alias for :class:`FactCheck` (PIR-856).

``*Gate`` is reserved for the framework's halt/pass primitive
(:class:`pirn.nodes.gate.gate.Gate`); this knot returns a
:class:`~pirn_agents.types.messaging.agent_response.AgentResponse`
annotated with a verification footer, which makes it an assessment knot per
Knot Design Rule 7, not a ``Gate``. Import :class:`FactCheck` instead — this
alias is kept only so existing imports keep working and will be removed in a
future release.
"""

from __future__ import annotations

import warnings
from typing import Any

from pirn_agents.specializations.guardrails.fact_check import FactCheck


class FactCheckGate(FactCheck):
    """Deprecated alias for :class:`FactCheck`. Import :class:`FactCheck` instead."""

    def __init__(self, **kwargs: Any) -> None:
        warnings.warn(
            "FactCheckGate is deprecated; use FactCheck instead (PIR-856). "
            "This alias will be removed in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(**kwargs)
