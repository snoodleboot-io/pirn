"""``InjectionDetectedError`` — content was judged a prompt-injection attempt."""

from __future__ import annotations

from pirn_agents.security.injection_verdict import InjectionVerdict


class InjectionDetectedError(Exception):
    """Raised by an injection screen when content is flagged and enforcement is on.

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
