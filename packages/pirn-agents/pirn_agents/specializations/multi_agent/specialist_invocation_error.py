"""``SpecialistInvocationError`` — a delegated specialist did not produce a value."""

from __future__ import annotations


class SpecialistInvocationError(Exception):
    """Raised when a specialist ``SubTapestry`` completes without an output.

    A specialist is invoked through :meth:`SubTapestry.__call__`, which never
    raises: it captures a failing inner run as ``Err`` and a deliberate opt-out
    as ``Skipped``. Neither carries a value, so the caller cannot go on, and
    swallowing that fact is what this error exists to prevent — the multi-agent
    pipelines that call specialists previously coerced whatever they got into
    an ``AgentResponse`` and reported success.

    Raising here restores the pre-existing failure semantics of the direct
    ``process()`` call this replaced: the exception escapes the calling
    pipeline's ``process()``, and the engine records it against that pipeline's
    knot id.

    Parameters
    ----------
    specialist_id:
        Knot id of the specialist that produced no value.
    reason:
        Human-readable description of why — the exception type and message for
        a failure, the skip reason for an opt-out.
    """

    def __init__(self, specialist_id: str, reason: str) -> None:
        self.specialist_id = specialist_id
        self.reason = reason
        super().__init__(f"specialist {specialist_id!r} produced no output: {reason}")
