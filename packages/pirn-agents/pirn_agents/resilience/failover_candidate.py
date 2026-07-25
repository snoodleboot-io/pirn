"""``FailoverCandidate`` — one named, timeout-bounded operation in a chain."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class FailoverCandidate(PirnOpaqueValue):
    """One provider/tool candidate in an ordered failover chain.

    A frozen value pairing a stable ``name`` (used for circuit-breaker scoping
    and trace records) with a zero-argument async ``operation`` and an optional
    per-candidate ``timeout``. The operation is opaque to pirn IO (it holds a
    live closure), which is why this wrapper is a :class:`PirnOpaqueValue`.

    Attributes
    ----------
    name:
        Stable identity of the candidate; also the circuit-breaker key.
    operation:
        Zero-arg async callable performing the actual call. Bind any arguments
        into the closure at chain-construction time.
    timeout:
        Per-candidate wall-clock ceiling in seconds, or ``None`` for no bound.
    """

    name: str
    operation: Callable[[], Awaitable[Any]]
    timeout: float | None = None

    def __post_init__(self) -> None:
        """Validate the name, operation, and optional timeout."""
        if not isinstance(self.name, str) or not self.name:
            raise ValueError(f"FailoverCandidate: name must be a non-empty str, got {self.name!r}")
        if not callable(self.operation):
            raise TypeError(
                f"FailoverCandidate: operation must be callable, "
                f"got {type(self.operation).__name__}"
            )
        timeout = self.timeout
        if timeout is not None and (
            isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0
        ):
            raise ValueError(
                f"FailoverCandidate: timeout must be a positive number or None, got {timeout!r}"
            )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"name": self.name, "timeout": self.timeout}
