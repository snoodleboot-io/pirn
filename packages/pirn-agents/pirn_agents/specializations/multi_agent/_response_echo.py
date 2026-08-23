"""``_ResponseEcho`` — a deliberate ceremonial pass-through knot.

This knot is **intentionally not a transform**. It exists for one reason: to
give a SubTapestry a Knot to return when the real work is already done, so that
the finished result still appears as a node in the run history rather than
vanishing. It computes nothing — ``process`` returns the very
:class:`AgentResponse` it was handed.

Its sole consumer is :mod:`round_robin_review` (a *sequential* reviewer chain):
``RoundRobinReview.process`` runs the reviewers itself and already holds the
final ``AgentResponse``, but its ``process(**) -> Knot`` contract requires it to
hand back a Knot. Recomputing anything would be wrong (the reviewers have run),
so it wraps the final response in a ``_ResponseEcho`` — a visible, do-nothing
terminal in history.

If you are here because this looked like an accident or dead code: it is
neither. Do not "fix" it into a real transform, and do not delete it — it is
pinned importable by ``tests/types/test_s6_import_surface.py`` (the WS5·S6
import-surface contract).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.types.messaging.agent_response import AgentResponse


class _ResponseEcho(Knot):
    """Ceremonial pass-through: returns the supplied AgentResponse unchanged.

    Deliberately not a transform. Its only job is to make an already-computed
    response visible as a terminal knot in run history (see the module
    docstring). Consumed only by ``round_robin_review``.
    """

    def __init__(
        self,
        *,
        response: Knot | AgentResponse,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(response=response, _config=_config, **kwargs)

    async def process(self, response: AgentResponse, **_: Any) -> AgentResponse:
        return response
