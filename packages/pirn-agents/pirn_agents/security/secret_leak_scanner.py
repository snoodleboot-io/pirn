"""``SecretLeakScanner`` — detect + redact secrets in free text.

Reuses the pirn-core :class:`~pirn.connectors.dsn_scrubber.DsnScrubber` for
DSN/URL credentials and layers on format-based patterns for the other common
shapes — AWS access-key ids, ``Authorization: Bearer`` headers, JWTs, PEM
private-key blocks, and ``key = value`` secret assignments. Every pattern is
*format*-based (never vendor-specific), so detection stays provider-neutral.

:meth:`redact_text` returns the scrubbed string plus the kinds it redacted;
:meth:`scan_text` reports the kinds without modifying the input. Structured
redaction of tool args / results is layered on top by
:class:`~pirn_agents.security.secret_redactor.SecretRedactor`.
"""

from __future__ import annotations

from collections.abc import Sequence
from re import IGNORECASE, Pattern
from re import compile as re_compile

from pirn.connectors.dsn_scrubber import DsnScrubber


class SecretLeakScanner:
    """Detect and redact secrets in strings, reusing :class:`DsnScrubber`."""

    def __init__(
        self,
        *,
        scrubber: DsnScrubber | None = None,
        extra_patterns: Sequence[tuple[str, str]] | None = None,
        placeholder: str = "<redacted>",
    ) -> None:
        """Configure the scanner.

        Args:
            scrubber: DSN scrubber to reuse; a default one is built when ``None``.
            extra_patterns: Optional additional ``(kind, regex)`` pairs.
            placeholder: The replacement token written over each secret.

        Raises:
            TypeError: If ``scrubber`` is not a :class:`DsnScrubber`.
        """
        if scrubber is not None and not isinstance(scrubber, DsnScrubber):
            raise TypeError("SecretLeakScanner: scrubber must be a DsnScrubber")
        self._scrubber = scrubber if scrubber is not None else DsnScrubber()
        self._placeholder = placeholder
        specs = self._defaults()
        if extra_patterns is not None:
            specs = [*specs, *extra_patterns]
        self._patterns: tuple[tuple[str, Pattern[str]], ...] = tuple(
            (kind, re_compile(regex, IGNORECASE)) for kind, regex in specs
        )

    @staticmethod
    def _defaults() -> list[tuple[str, str]]:
        """Return the default ``(kind, regex)`` secret patterns."""
        return [
            (
                "private_key",
                r"(?s)-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----.*?"
                r"-----END (?:[A-Z ]+ )?PRIVATE KEY-----",
            ),
            ("aws_key", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
            ("jwt", r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
            ("authorization", r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?[A-Za-z0-9._~+/=-]{8,}"),
            (
                "assignment",
                r"(?i)((?:api[_-]?key|secret[_-]?key|access[_-]?key|client[_-]?secret|"
                r"secret|token|password|passwd|pwd)\s*[:=]\s*)"
                r"[\"']?[A-Za-z0-9._~+/=-]{6,}[\"']?",
            ),
        ]

    def scan_text(self, text: str) -> tuple[str, ...]:
        """Return the kinds of secret found in ``text`` (input unchanged).

        Raises:
            TypeError: If ``text`` is not a string.
        """
        _, kinds = self.redact_text(text)
        return kinds

    def redact_text(self, text: str) -> tuple[str, tuple[str, ...]]:
        """Return ``(redacted_text, kinds)`` for ``text``.

        The DSN scrubber runs first, then each format pattern; assignment- and
        header-style matches keep their key/prefix and redact only the value.

        Raises:
            TypeError: If ``text`` is not a string.
        """
        if not isinstance(text, str):
            raise TypeError(f"SecretLeakScanner: text must be a str, got {type(text).__name__}")
        kinds: list[str] = []
        scrubbed = self._scrubber.scrub(text)
        if scrubbed != text:
            kinds.append("dsn")
        for kind, pattern in self._patterns:
            if pattern.search(scrubbed) is None:
                continue
            kinds.append(kind)
            if kind in ("authorization", "assignment"):
                scrubbed = pattern.sub(rf"\1{self._placeholder}", scrubbed)
            else:
                scrubbed = pattern.sub(self._placeholder, scrubbed)
        return scrubbed, tuple(kinds)

    def has_secret(self, text: str) -> bool:
        """Return whether ``text`` contains any detectable secret."""
        return bool(self.scan_text(text))
