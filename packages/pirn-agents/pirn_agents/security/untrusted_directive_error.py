"""``UntrustedDirectiveError`` — untrusted content tried to steer the agent."""

from __future__ import annotations


class UntrustedDirectiveError(Exception):
    """Raised when untrusted content attempts to direct the agent.

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
