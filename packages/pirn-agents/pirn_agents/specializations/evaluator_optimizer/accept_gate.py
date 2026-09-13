"""``AcceptGate`` — deprecated alias for :class:`AcceptCheck` (PIR-856).

``*Gate`` is reserved for the framework's halt/pass primitive
(:class:`pirn.nodes.gate.gate.Gate`); this knot returns an accept/reject
boolean from a threshold comparison, which makes it an assessment knot per
Knot Design Rule 7, not a ``Gate``. Import :class:`AcceptCheck` instead —
this alias is kept only so existing imports keep working and will be removed
in a future release.
"""

from __future__ import annotations

import warnings
from typing import Any

from pirn_agents.specializations.evaluator_optimizer.accept_check import AcceptCheck


class AcceptGate(AcceptCheck):
    """Deprecated alias for :class:`AcceptCheck`. Import :class:`AcceptCheck` instead."""

    def __init__(self, **kwargs: Any) -> None:
        warnings.warn(
            "AcceptGate is deprecated; use AcceptCheck instead (PIR-856). "
            "This alias will be removed in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(**kwargs)
