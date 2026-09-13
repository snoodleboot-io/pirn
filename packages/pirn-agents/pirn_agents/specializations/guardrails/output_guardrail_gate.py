"""``OutputGuardrailGate`` — deprecated alias for :class:`OutputGuardrailCheck` (PIR-856).

``*Gate`` is reserved for the framework's halt/pass primitive
(:class:`pirn.nodes.gate.gate.Gate`); this knot returns a validated
:class:`~pirn_agents.types.messaging.agent_response.AgentResponse`, which
makes it an assessment knot per Knot Design Rule 7, not a ``Gate``. Import
:class:`OutputGuardrailCheck` instead — this alias is kept only so existing
imports keep working and will be removed in a future release.
"""

from __future__ import annotations

import warnings
from typing import Any

from pirn_agents.specializations.guardrails.output_guardrail_check import (
    OutputGuardrailCheck,
)


class OutputGuardrailGate(OutputGuardrailCheck):
    """Deprecated alias for :class:`OutputGuardrailCheck`. Import that instead."""

    def __init__(self, **kwargs: Any) -> None:
        warnings.warn(
            "OutputGuardrailGate is deprecated; use OutputGuardrailCheck instead "
            "(PIR-856). This alias will be removed in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(**kwargs)
