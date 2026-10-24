"""``FailoverResult`` — the typed outcome of a failover-chain run.

PIR-874 completes the PIR-868 rebase for this type: ``FailoverResult`` is
``Payload[FailoverFrame, Any]``. The frame
(:class:`~pirn_agents.resilience.failover_frame.FailoverFrame`) carries
``succeeded``/``chosen`` and the ``attempts`` trace; ``data`` is the winning
candidate's return value.
"""

from __future__ import annotations

from typing import Any

from pirn_agents.resilience.failover_attempt import FailoverAttempt
from pirn_agents.resilience.failover_frame import FailoverFrame
from pirn_agents.specializations.base.agent_result import AgentResult


class FailoverResult(AgentResult[FailoverFrame, Any]):
    """Outcome of walking an ordered failover chain until one candidate wins.

    The ``attempts`` trace (``metadata.attempts``) holds one
    :class:`FailoverAttempt` per candidate considered, in order, so callers can
    see which candidates were tried and why each earlier one fell through.
    Read ``succeeded``, ``chosen`` and ``attempts`` as ``metadata.<field>`` and
    the winning value as ``data`` (``None`` on exhaustion; a candidate that
    legitimately returns ``None`` still sets ``succeeded=True``).
    """

    def __init__(
        self,
        succeeded: bool,
        chosen: str | None,
        value: Any,
        attempts: tuple[FailoverAttempt, ...],
    ) -> None:
        """Build a result from the walk's facts and the winning value.

        Args:
            succeeded: Whether some candidate returned a value.
            chosen: The winning candidate's name, or ``None`` on exhaustion.
            value: The winning candidate's return value, or ``None``. Stored as
                ``data``.
            attempts: Ordered trace of every candidate considered.
        """
        frame = FailoverFrame(succeeded=succeeded, chosen=chosen, attempts=attempts)
        super().__init__(metadata=frame, data=value)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["value"] = repr(self.data)
        return audit
