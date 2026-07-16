"""``parse_binary_verdict`` — read a yes/no judgement from a judge's free text."""

from __future__ import annotations


def parse_binary_verdict(text: str) -> bool:
    """Interpret a judge's free-text reply as a boolean yes/no verdict.

    Provider-neutral and lenient: it first inspects the leading token (the
    common ``"Yes, ..."`` / ``"No — ..."`` shape), then falls back to scanning
    for affirmative vs negative markers, preferring an explicit negative so a
    reply like ``"not supported"`` reads as ``False``. Anything with no
    recognisable signal is treated as ``False`` (fail closed).

    Args:
        text: The judge's reply text.

    Returns:
        ``True`` for an affirmative verdict, ``False`` otherwise.

    Raises:
        TypeError: If ``text`` is not a ``str``.
    """
    if not isinstance(text, str):
        raise TypeError(f"parse_binary_verdict: text must be a str, got {type(text).__name__}")
    lowered = text.strip().lower()
    if not lowered:
        return False
    negatives = {"no", "not", "false", "0", "unsupported", "irrelevant", "unfaithful", "incorrect"}
    positives = {"yes", "true", "1", "supported", "relevant", "faithful", "correct", "attributed"}
    first = lowered.split()[0].strip(".,!:;\"'")
    if first in negatives:
        return False
    if first in positives:
        return True
    if any(marker in lowered for marker in ("not supported", "unsupported", "irrelevant")):
        return False
    return any(marker in lowered for marker in ("supported", "relevant", "faithful", "yes"))
