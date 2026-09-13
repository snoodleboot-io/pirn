"""``UntrustedDirectiveError`` — untrusted content tried to steer the agent."""

from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class UntrustedDirectiveError(PirnError, Exception):
    """Raised when untrusted content attempts to direct the agent.

    Subclasses :class:`~pirn.exceptions.pirn_error.PirnError` in addition to
    ``Exception`` so every existing ``except Exception`` handler keeps
    working unchanged, while new code can narrow to ``PirnError``.

    Carries the human-readable ``message`` and the tuple of matched
    ``directives`` (the offending snippets) so a caller can log or surface
    exactly what tripped the no-silent-invocation policy.

    Parameters
    ----------
    message:
        Human-readable description of the violation.
    directives:
        The directive snippets detected in the untrusted content.
    """

    def __init__(self, message: str, directives: tuple[str, ...] = ()) -> None:
        self.message = message
        self.directives = directives
        super().__init__(message)
