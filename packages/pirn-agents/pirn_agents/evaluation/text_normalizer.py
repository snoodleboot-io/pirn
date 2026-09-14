"""``TextNormalizer`` — shared case/whitespace normalisation for text metrics."""

from __future__ import annotations


class TextNormalizer:
    """Normalise text for tolerant string comparison (case/whitespace)."""

    def __init__(
        self,
        *,
        lower: bool = True,
        collapse_whitespace: bool = True,
        strip: bool = True,
    ) -> None:
        """Configure which normalisation steps to apply.

        Args:
            lower: Lower-case the text when ``True``.
            collapse_whitespace: Replace every internal whitespace run with a
                single space when ``True``.
            strip: Strip leading/trailing whitespace when ``True``.
        """
        self._lower = lower
        self._collapse_whitespace = collapse_whitespace
        self._strip = strip

    def normalize(self, text: str) -> str:
        """Return ``text`` normalised for tolerant string comparison.

        Applies, in order: optional lower-casing, optional collapsing of every
        run of whitespace to a single space, and optional stripping of
        leading/trailing whitespace. Metrics that compare surface strings route
        through this so a trailing newline or double space does not register as
        a mismatch.

        Args:
            text: The string to normalise.

        Returns:
            The normalised string.

        Raises:
            TypeError: If ``text`` is not a ``str``.
        """
        if not isinstance(text, str):
            raise TypeError(f"TextNormalizer: text must be a str, got {type(text).__name__}")
        out = text
        if self._lower:
            out = out.lower()
        if self._collapse_whitespace:
            out = " ".join(out.split())
        if self._strip:
            out = out.strip()
        return out
