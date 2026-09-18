"""``FailoverAttempt`` — one trace record in a failover run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from pirn.core.err import Err
from pirn.core.ok import Ok
from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.core.result import Result
from pirn.core.skipped import Skipped


@dataclass(frozen=True)
class FailoverAttempt(PirnOpaqueValue):
    """The traced disposition of a single candidate during a failover run.

    ``result`` is a core :class:`~pirn.core.result.Result` (ADR
    agents-speaks-core WS5a): ``Ok(value)`` on success, ``Err(record)`` on a raised exception
    or timeout (a timeout is the ``Err`` whose error type is ``KnotTimeoutError``,
    recorded by the engine for a call that outlived ``KnotConfig.timeout``),
    ``Skipped(reason=circuit_open_reason)`` when the circuit breaker was open
    and no call was attempted at all — which is exactly the distinction
    ``Skipped`` exists to make (``pirn/core/skipped.py``: "distinct from Err so
    downstream knots can treat skip-vs-fail differently").

    Attributes:
        name: The candidate's stable identity.
        result: The candidate's outcome.
    """

    #: The ``Skipped.reason`` a candidate whose circuit breaker was open records.
    circuit_open_reason: ClassVar[str] = "circuit_open"

    name: str
    result: Result[Any]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Render the attempt for a trace: the ``Result`` variant plus its error type or reason."""
        result = self.result
        if isinstance(result, Ok):
            return {"name": self.name, "outcome": "ok", "error_type": None, "error": None}
        if isinstance(result, Skipped):
            return {
                "name": self.name,
                "outcome": "skipped",
                "error_type": None,
                "error": result.reason,
            }
        assert isinstance(result, Err)
        return {
            "name": self.name,
            "outcome": "err",
            "error_type": result.record.exc_type,
            "error": result.record.message,
        }
