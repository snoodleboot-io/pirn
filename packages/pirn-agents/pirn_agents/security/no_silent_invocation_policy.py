"""``NoSilentInvocationPolicy`` — untrusted data may not steer the agent.

The wrapping in S1 makes untrusted content *visible*; this policy makes it
*inert*. It scans an
:class:`~pirn_agents.security.untrusted_content.UntrustedContent` (or raw string)
for embedded directives that try to trigger new tool calls or override the
system instructions — the core indirect-prompt-injection move — and either
reports the matches (:meth:`detect`) or refuses (:meth:`enforce`).

It complements S2's :class:`~pirn_agents.security.injection_screen.InjectionScreen`
by focusing narrowly on the *tool-invocation / instruction-override* class the
story calls out; the patterns are instance state (validated at ``__init__``) so
callers can extend them without any module-level constant.
"""

from __future__ import annotations

from collections.abc import Sequence
from re import Pattern

from pirn_agents._safe_pattern_compiler import SafePatternCompiler
from pirn_agents.security.untrusted_content import UntrustedContent
from pirn_agents.security.untrusted_directive_error import UntrustedDirectiveError


class NoSilentInvocationPolicy:
    """Detect / block untrusted content that tries to trigger tools or override rules."""

    def __init__(self, *, directive_patterns: Sequence[str] | None = None) -> None:
        """Compile the directive patterns used to spot injected instructions.

        Args:
            directive_patterns: Optional override for the default regex set. Each
                entry is compiled case-insensitively via
                :meth:`~pirn_agents._safe_pattern_compiler.SafePatternCompiler.compile_safe_pattern`.

        Raises:
            ValueError: If any supplied pattern is not valid regex.
        """
        self._pattern_compiler = SafePatternCompiler()
        raw = list(directive_patterns) if directive_patterns is not None else self._defaults()
        self._patterns: tuple[Pattern[str], ...] = tuple(
            self._pattern_compiler.compile_safe_pattern(
                pattern,
                index=index,
                owner="NoSilentInvocationPolicy",
                field="directive_patterns",
            )
            for index, pattern in enumerate(raw)
        )

    @staticmethod
    def _defaults() -> list[str]:
        """Return the default indirect-injection directive patterns."""
        return [
            r"(?i)ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions",
            r"(?i)disregard\s+(?:the\s+)?(?:above|previous|system)",
            r"(?i)forget\s+(?:everything|all\s+previous)",
            r"(?i)you\s+are\s+now\s+(?:a|an|in)\b",
            r"(?i)new\s+(?:system\s+)?(?:instructions?|rules?|prompt)\s*:",
            r"(?i)\b(?:call|invoke|run|use|execute)\s+the\s+[\w.-]+\s+tool\b",
            r"(?i)\b(?:call|invoke|run|execute)\s+[\w.-]+\(",
            r"(?i)system\s*:\s*",
            r"(?i)override\s+(?:the\s+)?(?:system|instructions?|policy)",
            r"(?i)reveal\s+(?:your\s+)?(?:system\s+prompt|instructions?)",
        ]

    def detect(self, content: UntrustedContent | str) -> tuple[str, ...]:
        """Return the directive snippets found in ``content``.

        Args:
            content: An :class:`UntrustedContent` or raw string to scan. The
                *original* payload is scanned, not the rendered block, so the
                wrapper's own spotlight note never trips the policy.

        Returns:
            A tuple of matched snippets (empty when the content is inert).

        Raises:
            TypeError: If ``content`` is neither an :class:`UntrustedContent`
                nor a string.
        """
        text = self._text_of(content)
        matches: list[str] = []
        for pattern in self._patterns:
            for found in pattern.findall(text):
                snippet = found if isinstance(found, str) else " ".join(found)
                matches.append(snippet.strip())
        return tuple(matches)

    def is_inert(self, content: UntrustedContent | str) -> bool:
        """Return whether ``content`` contains no steering directives."""
        return not self.detect(content)

    def enforce(self, content: UntrustedContent | str) -> None:
        """Raise if ``content`` tries to trigger tools or override instructions.

        Args:
            content: The untrusted content to vet.

        Raises:
            UntrustedDirectiveError: If any directive pattern matches.
            TypeError: If ``content`` is of an unsupported type.
        """
        directives = self.detect(content)
        if directives:
            raise UntrustedDirectiveError(
                "NoSilentInvocationPolicy: untrusted content attempted to direct the agent",
                directives=directives,
            )

    @staticmethod
    def _text_of(content: UntrustedContent | str) -> str:
        """Return the raw payload text of ``content``."""
        if isinstance(content, UntrustedContent):
            return content.payload
        if isinstance(content, str):
            return content
        raise TypeError(
            f"NoSilentInvocationPolicy: content must be UntrustedContent or str, "
            f"got {type(content).__name__}"
        )
