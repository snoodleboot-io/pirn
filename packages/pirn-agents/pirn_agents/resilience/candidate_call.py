"""``CandidateCall`` — run one failover candidate's operation as its own knot.

The candidate's ``timeout`` is this knot's ``KnotConfig.timeout``, so the engine
bounds the call and records an overrun as ``Err(KnotTimeoutError)``.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.resilience.failover_candidate import FailoverCandidate


class CandidateCall(Knot):
    """Await ``candidate.operation()`` and return its value."""

    def __init__(
        self, *, candidate: Knot | FailoverCandidate, _config: KnotConfig, **kwargs: Any
    ) -> None:
        super().__init__(candidate=candidate, _config=_config, **kwargs)

    async def process(self, candidate: FailoverCandidate, **_: Any) -> Any:
        """Call the candidate.

        Args:
            candidate: The candidate whose zero-argument operation runs.

        Returns:
            Whatever the operation returns.
        """
        return await candidate.operation()
