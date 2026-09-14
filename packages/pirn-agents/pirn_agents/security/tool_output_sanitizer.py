"""``ToolOutputSanitizer`` — clean tool output before it re-enters the prompt.

The sanitizer runs three cheap, inline passes over a raw tool payload:

1. **Control-sequence stripping.** ANSI/CSI escape sequences and C0/C1 control
   characters (except the ordinary ``\\t`` and ``\\n`` whitespace) are removed —
   they can smuggle terminal-escape or bidi tricks into a transcript.
2. **Active-content quarantine.** Delegated to
   :class:`~pirn_agents.security.active_content_quarantine.ActiveContentQuarantine`,
   which replaces scripts / URIs / URLs with inert placeholders.
3. **Size cap.** The result is truncated at ``max_chars`` so a hostile or
   runaway tool cannot blow the context window.

The outcome is a frozen
:class:`~pirn_agents.security.sanitized_output.SanitizedOutput` recording exactly
what changed, so nothing is silently dropped.
"""

from __future__ import annotations

from re import Pattern
from re import compile as re_compile

from pirn_agents.security.active_content_quarantine import ActiveContentQuarantine
from pirn_agents.security.sanitized_output import SanitizedOutput


class ToolOutputSanitizer:
    """Strip control sequences, quarantine active content, and cap tool output size."""

    def __init__(
        self,
        *,
        max_chars: int = 100_000,
        quarantine: ActiveContentQuarantine | None = None,
        strip_controls: bool = True,
    ) -> None:
        """Configure the sanitizer.

        Args:
            max_chars: Maximum characters kept before truncation (> 0).
            quarantine: The active-content quarantine to apply; a default one is
                built when ``None``.
            strip_controls: When ``True`` (default), remove control sequences.

        Raises:
            TypeError: If ``quarantine`` is not an :class:`ActiveContentQuarantine`.
            ValueError: If ``max_chars`` is not positive.
        """
        if max_chars <= 0:
            raise ValueError(f"ToolOutputSanitizer: max_chars must be positive, got {max_chars}")
        if quarantine is not None and not isinstance(quarantine, ActiveContentQuarantine):
            raise TypeError("ToolOutputSanitizer: quarantine must be an ActiveContentQuarantine")
        self._max_chars = max_chars
        self._strip_controls = strip_controls
        self._quarantine = quarantine if quarantine is not None else ActiveContentQuarantine()
        # ANSI/CSI escape sequences, then remaining C0 (minus \t\n) and C1 controls.
        self._ansi_re: Pattern[str] = re_compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[@-Z\\-_]")
        self._control_re: Pattern[str] = re_compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

    def sanitize(self, output: str) -> SanitizedOutput:
        """Sanitize ``output`` and return a :class:`SanitizedOutput`.

        Args:
            output: The raw tool output text.

        Returns:
            The sanitized result, recording stripped/truncated/quarantined state.

        Raises:
            TypeError: If ``output`` is not a string.
        """
        if not isinstance(output, str):
            raise TypeError(
                f"ToolOutputSanitizer: output must be a str, got {type(output).__name__}"
            )
        original_length = len(output)
        text, stripped = self._strip(output)
        text, items = self._quarantine.quarantine(text)
        text, truncated = self._cap(text)
        return SanitizedOutput(
            text=text,
            original_length=original_length,
            truncated=truncated,
            stripped=stripped,
            quarantined=items,
        )

    def _strip(self, text: str) -> tuple[str, int]:
        """Remove control sequences; return the cleaned text and removed count."""
        if not self._strip_controls:
            return text, 0
        without_ansi = self._ansi_re.sub("", text)
        cleaned = self._control_re.sub("", without_ansi)
        removed = len(text) - len(cleaned)
        return cleaned, removed

    def _cap(self, text: str) -> tuple[str, bool]:
        """Truncate ``text`` at ``max_chars``; return the text and whether it was cut."""
        if len(text) <= self._max_chars:
            return text, False
        return text[: self._max_chars], True
