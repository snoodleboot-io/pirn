"""``BinaryVerdictParser`` — read a yes/no judgement from a judge's free text."""

from __future__ import annotations

from pirn_agents.evaluation.affirmative_verdict_word import AffirmativeVerdictWord
from pirn_agents.evaluation.negative_verdict_word import NegativeVerdictWord


class BinaryVerdictParser:
    """Interpret a judge's free-text reply as a boolean yes/no verdict."""

    def __init__(self) -> None:
        """Resolve both verdict vocabularies once, as instance state.

        The two roles are held separately because they are matched differently:
        the token sets are compared against the reply's leading word, the marker
        tuples are scanned as substrings anywhere in the reply.
        """
        self._negative_tokens: frozenset[str] = NegativeVerdictWord.leading_tokens()
        self._affirmative_tokens: frozenset[str] = AffirmativeVerdictWord.leading_tokens()
        self._negative_markers: tuple[str, ...] = NegativeVerdictWord.scan_markers()
        self._affirmative_markers: tuple[str, ...] = AffirmativeVerdictWord.scan_markers()

    def parse(self, text: str) -> bool:
        """Interpret a judge's free-text reply as a boolean yes/no verdict.

        Provider-neutral and lenient: it first inspects the leading token (the
        common ``"Yes, ..."`` / ``"No — ..."`` shape), then falls back to
        scanning for affirmative vs negative markers, preferring an explicit
        negative so a reply like ``"not supported"`` reads as ``False``.
        Anything with no recognisable signal is treated as ``False`` (fail
        closed).

        Args:
            text: The judge's reply text.

        Returns:
            ``True`` for an affirmative verdict, ``False`` otherwise.

        Raises:
            TypeError: If ``text`` is not a ``str``.
        """
        if not isinstance(text, str):
            raise TypeError(f"BinaryVerdictParser: text must be a str, got {type(text).__name__}")
        lowered = text.strip().lower()
        if not lowered:
            return False
        first = lowered.split()[0].strip(".,!:;\"'")
        if first in self._negative_tokens:
            return False
        if first in self._affirmative_tokens:
            return True
        if any(marker in lowered for marker in self._negative_markers):
            return False
        return any(marker in lowered for marker in self._affirmative_markers)
