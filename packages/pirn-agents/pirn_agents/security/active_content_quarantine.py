"""``ActiveContentQuarantine`` — pull active content out of tool output.

Tool / RAG / MCP payloads may embed content that an agent (or a downstream
renderer) could be lured into *acting on*: ``<script>`` blocks, ``javascript:``
and ``data:`` URIs, inline ``on*=`` event handlers, and bare ``http(s)`` URLs a
model might auto-follow. This class detects those spans and replaces each with
an inert ``[QUARANTINED:<kind>#<n>]`` placeholder, returning the removed spans as
:class:`~pirn_agents.security.quarantined_item.QuarantinedItem`s so nothing is
silently dropped.

Patterns are applied highest-risk first (scripts, then URIs, then handlers, then
bare URLs); because each replacement is an inert token, later patterns never
re-match an already-quarantined span. Patterns are instance state so callers can
extend them with no module-level constant.
"""

from __future__ import annotations

from collections.abc import Sequence
from re import DOTALL, IGNORECASE, Match, Pattern

from pirn_agents._safe_pattern_compiler import SafePatternCompiler
from pirn_agents.security.quarantined_item import QuarantinedItem


class ActiveContentQuarantine:
    """Detect and defang active content in untrusted tool output."""

    def __init__(self, *, extra_patterns: Sequence[tuple[str, str]] | None = None) -> None:
        """Compile the active-content patterns.

        Args:
            extra_patterns: Optional additional ``(kind, regex)`` pairs appended
                after the defaults (matched at lower priority).

        Raises:
            ValueError: If any supplied regex is invalid.
        """
        self._pattern_compiler = SafePatternCompiler()
        specs = self._defaults()
        if extra_patterns is not None:
            specs = [*specs, *extra_patterns]
        self._patterns: tuple[tuple[str, Pattern[str]], ...] = tuple(
            (
                kind,
                self._pattern_compiler.compile_safe_pattern(
                    regex,
                    index=index,
                    owner="ActiveContentQuarantine",
                    field="patterns",
                    flags=IGNORECASE | DOTALL,
                ),
            )
            for index, (kind, regex) in enumerate(specs)
        )

    @staticmethod
    def _defaults() -> list[tuple[str, str]]:
        """Return the default ``(kind, regex)`` active-content specs, highest-risk first."""
        return [
            ("script", r"<script\b[^>]*>.*?</script\s*>"),
            ("script", r"<script\b[^>]*/?>"),
            ("javascript_uri", r"javascript:[^\s\"'<>)]+"),
            ("data_uri", r"data:[^\s\"'<>)]+"),
            ("event_handler", r"\bon[a-z]+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)"),
            ("url", r"https?://[^\s\"'<>)\]]+"),
        ]

    def scan(self, text: str) -> tuple[QuarantinedItem, ...]:
        """Return the active-content items in ``text`` without modifying it.

        Raises:
            TypeError: If ``text`` is not a string.
        """
        _, items = self.quarantine(text)
        return items

    def quarantine(self, text: str) -> tuple[str, tuple[QuarantinedItem, ...]]:
        """Replace active content with inert placeholders.

        Args:
            text: The (already control-stripped) tool output to defang.

        Returns:
            A ``(defanged_text, items)`` pair; ``items`` holds every removed
            span in the order encountered.

        Raises:
            TypeError: If ``text`` is not a string.
        """
        if not isinstance(text, str):
            raise TypeError(
                f"ActiveContentQuarantine: text must be a str, got {type(text).__name__}"
            )
        items: list[QuarantinedItem] = []
        working = text
        for kind, pattern in self._patterns:

            def _replace(match: Match[str], _kind: str = kind) -> str:
                value = match.group(0)
                placeholder = f"[QUARANTINED:{_kind}#{len(items)}]"
                items.append(QuarantinedItem(kind=_kind, value=value, placeholder=placeholder))
                return placeholder

            working = pattern.sub(_replace, working)
        return working, tuple(items)
