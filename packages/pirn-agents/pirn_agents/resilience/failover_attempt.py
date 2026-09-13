"""``FailoverAttempt`` — one trace record in a failover run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.err import Err
from pirn.core.ok import Ok
from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.core.result import Result
from pirn.core.skipped import Skipped

from pirn_agents.resilience.failover_outcome import FailoverOutcome


@dataclass(frozen=True)
class FailoverAttempt(PirnOpaqueValue):
    """The traced disposition of a single candidate during a failover run.

    ``result`` is a core :class:`~pirn.core.result.Result` (ADR
    agents-speaks-core WS5a) rather than the historical
    :class:`FailoverOutcome` enum + separate ``error`` string: ``Ok(value)``
    on success, ``Err(record)`` on a raised exception or timeout (the two
    ``FailoverOutcome`` members that were always failures under a different
    name), ``Skipped`` when the circuit breaker was open and no call was
    attempted at all — which is exactly the distinction ``Skipped`` exists
    to make (``pirn/core/skipped.py``: "distinct from Err so downstream knots
    can treat skip-vs-fail differently").

    Attributes:
        name: The candidate's stable identity.
        result: The candidate's outcome.
    """

    name: str
    result: Result[Any]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        result = self.result
        if isinstance(result, Ok):
            return {"name": self.name, "outcome": FailoverOutcome.SUCCESS.value, "error": None}
        if isinstance(result, Skipped):
            return {
                "name": self.name,
                "outcome": FailoverOutcome.CIRCUIT_OPEN.value,
                "error": result.reason,
            }
        assert isinstance(result, Err)
        outcome = (
            FailoverOutcome.TIMEOUT.value
            if result.record.exc_type == "TimeoutError"
            else FailoverOutcome.ERROR.value
        )
        return {"name": self.name, "outcome": outcome, "error": result.record.message}
