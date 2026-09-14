"""``CandidateRejectedCheck`` — should the reflection check run this iteration?

The ``Check`` (core role, ``pirn.nodes.check.Check``) behind the
:class:`~pirn.nodes.gate.gate.Gate` that keeps
:class:`~pirn_agents.control.reflection_check.ReflectionCheck`'s LLM call from
running on an accepted candidate: ``Gate(input=candidate, check=...)`` gates
the candidate itself, so when this check is ``False`` the gated candidate is
``Skipped`` and everything downstream of it — the reflection call — is skipped
with it, never paying for the call.

Algorithm:
    1. Receive the resolved ``accepted`` verdict of ``AcceptCheck``.
    2. Return ``not accepted``.

Internal API. See PIR-872.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.check import Check


class CandidateRejectedCheck(Check):
    """``True`` when the judge's verdict did not clear the accept threshold."""

    def __init__(
        self,
        *,
        accepted: Knot | bool,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(accepted=accepted, _config=_config, **kwargs)

    async def process(self, accepted: bool, **_: Any) -> bool:
        """Return whether the candidate was rejected.

        Args:
            accepted: ``AcceptCheck``'s verdict for this iteration's candidate.

        Returns:
            ``True`` when ``accepted`` is ``False``.
        """
        return not accepted
