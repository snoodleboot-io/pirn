"""``PairwiseChoiceParser`` — read an A/B/tie verdict from judge free text."""

from __future__ import annotations


class PairwiseChoiceParser:
    """Interpret a judge's reply as which presented response won: a/b/tie."""

    def parse(self, text: str) -> str:
        """Interpret a judge's reply as which presented response won: ``a``/``b``/``tie``.

        The verdict refers to *presentation order* (the response shown first is
        ``"a"``); the caller maps it back to the real responses so position bias
        can be controlled. A reply naming a tie/draw returns ``"tie"``;
        otherwise the leading ``a``/``b`` token wins, falling back to whichever
        of ``"a"``/``"b"`` appears first in the text. An unreadable reply returns
        ``"tie"``.

        Args:
            text: The judge's reply text.

        Returns:
            One of ``"a"``, ``"b"``, or ``"tie"``.

        Raises:
            TypeError: If ``text`` is not a ``str``.
        """
        if not isinstance(text, str):
            raise TypeError(f"PairwiseChoiceParser: text must be a str, got {type(text).__name__}")
        lowered = text.strip().lower()
        if not lowered:
            return "tie"
        if any(marker in lowered for marker in ("tie", "equal", "draw", "neither", "both")):
            return "tie"
        first = lowered.split()[0].strip(".,!:;\"'()")
        if first in {"a", "response_a"}:
            return "a"
        if first in {"b", "response_b"}:
            return "b"
        index_a = lowered.find("a")
        index_b = lowered.find("b")
        if index_a == -1 and index_b == -1:
            return "tie"
        if index_b == -1 or (index_a != -1 and index_a < index_b):
            return "a"
        return "b"
