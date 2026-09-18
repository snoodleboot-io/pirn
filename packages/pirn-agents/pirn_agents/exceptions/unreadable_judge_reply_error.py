"""``UnreadableJudgeReplyError`` — a judge's reply carried no verdict this code can read."""

from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class UnreadableJudgeReplyError(PirnError, ValueError):
    """Raised when an LLM-as-judge reply states no readable verdict or score.

    Subclasses :class:`~pirn.exceptions.pirn_error.PirnError` in addition to
    ``ValueError`` so an existing ``except ValueError`` handler around judge
    parsing keeps working, while new code can narrow to ``PirnError``.

    The judge parsers used to answer anyway: a reply with no number scored
    ``0.0`` and a reply with no A/B/tie token returned ``"tie"``, so a provider
    outage, a refusal, or a reply in a shape the parser did not know produced a
    *number in the report* indistinguishable from a real judgement. An
    evaluation harness whose whole purpose is measurement must not invent
    measurements: an unreadable reply fails the evaluation instead (PIR-873).

    Attributes
    ----------
    reply:
        The reply text that could not be read, truncated for the message.
    expected:
        What the parser required, so the failure names the fix.
    """

    def __init__(self, reply: str, *, expected: str) -> None:
        self.reply = reply
        self.expected = expected
        shown = reply if len(reply) <= 120 else f"{reply[:117]}..."
        super().__init__(f"unreadable judge reply {shown!r}; expected {expected}")
