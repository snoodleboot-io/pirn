"""``SandboxResult`` — the typed outcome of one sandboxed execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class SandboxResult(PirnOpaqueValue):
    """Captured result of running a command/code inside the sandbox.

    Attributes
    ----------
    stdout:
        Captured standard output (already truncated to the output cap).
    stderr:
        Captured standard error (already truncated to the output cap).
    exit_code:
        Process exit status, or ``None`` when the process was killed (e.g. on
        timeout).
    timed_out:
        ``True`` when the process exceeded its hard timeout and was killed.
    truncated:
        ``True`` when stdout or stderr exceeded the output cap and was cut.
    """

    stdout: str
    stderr: str
    exit_code: int | None
    timed_out: bool
    truncated: bool

    def as_mapping(self) -> dict[str, Any]:
        """Return the result as a plain JSON-friendly mapping."""
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "truncated": self.truncated,
        }

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.as_mapping()
