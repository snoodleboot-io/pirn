"""``InputGuardrailGate`` — deprecated alias for :class:`InputGuardrailCheck` (PIR-856).

``*Gate`` is reserved for the framework's halt/pass primitive
(:class:`pirn.nodes.gate.gate.Gate`); this knot returns a cleaned tuple of
messages, which makes it an assessment/transform knot per Knot Design Rule 7,
not a ``Gate``. Import :class:`InputGuardrailCheck` instead — this alias is
kept only so existing imports keep working and will be removed in a future
release.
"""

from __future__ import annotations

import warnings
from typing import Any

from pirn_agents.specializations.guardrails.input_guardrail_check import (
    InputGuardrailCheck,
)


class InputGuardrailGate(InputGuardrailCheck):
    """Deprecated alias for :class:`InputGuardrailCheck`. Import that instead."""

    def __init__(self, **kwargs: Any) -> None:
        warnings.warn(
            "InputGuardrailGate is deprecated; use InputGuardrailCheck instead "
            "(PIR-856). This alias will be removed in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(**kwargs)
