"""``normalize_text`` — shared case/whitespace normalisation for text metrics."""

from __future__ import annotations


def normalize_text(
    text: str,
    *,
    lower: bool = True,
    collapse_whitespace: bool = True,
    strip: bool = True,
) -> str:
    """Return ``text`` normalised for tolerant string comparison.

    Applies, in order: optional lower-casing, optional collapsing of every run
    of whitespace to a single space, and optional stripping of leading/trailing
    whitespace. Metrics that compare surface strings route through this so a
    trailing newline or double space does not register as a mismatch.

    Args:
        text: The string to normalise.
        lower: Lower-case the text when ``True``.
        collapse_whitespace: Replace every internal whitespace run with a single
            space when ``True``.
        strip: Strip leading/trailing whitespace when ``True``.

    Returns:
        The normalised string.

    Raises:
        TypeError: If ``text`` is not a ``str``.
    """
    if not isinstance(text, str):
        raise TypeError(f"normalize_text: text must be a str, got {type(text).__name__}")
    out = text
    if lower:
        out = out.lower()
    if collapse_whitespace:
        out = " ".join(out.split())
    if strip:
        out = out.strip()
    return out
