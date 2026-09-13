"""``InjectionDetectedError`` — content was judged a prompt-injection attempt."""

from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError

from pirn_agents.security.injection_verdict import InjectionVerdict


class InjectionDetectedError(PirnError, Exception):
    """Raised by an injection screen when content is flagged and enforcement is on.

    Subclasses :class:`~pirn.exceptions.pirn_error.PirnError` in addition to
    ``Exception`` so every existing ``except Exception`` handler keeps
    working unchanged, while new code can narrow to ``PirnError``.

    Carries the :class:`~pirn_agents.security.injection_verdict.InjectionVerdict`
    that triggered the block so callers can log the score and matched snippets.

    Parameters
    ----------
    verdict:
        The flagged verdict that caused the refusal.
    """

    def __init__(self, verdict: InjectionVerdict) -> None:
        self.verdict = verdict
        super().__init__(f"InjectionScreen: blocked content ({verdict.reason})")
