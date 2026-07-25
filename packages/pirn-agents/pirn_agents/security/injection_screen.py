"""``InjectionScreen`` — the indirect-prompt-injection gate (F11-S2 / PIR-255).

A two-tier screen over untrusted content:

* **Heuristic tier (always inline).** A set of compiled regexes for the common
  indirect-injection moves (instruction override, tool-call directives, data
  exfiltration, system-prompt extraction). Each match adds weight; the score
  crossing an upper threshold flags the content. This is the happy path — pure
  regex, no round-trip.
* **Optional LLM tier (budgeted).** Only when the heuristic score lands *between*
  the lower and upper thresholds (genuinely ambiguous) **and** a
  :class:`~pirn_agents.security.llm_injection_classifier.LlmInjectionClassifier`
  is wired **and** the per-screen call budget is not exhausted does
  :meth:`ascreen` consult the LLM. A default screen (no classifier, budget 0)
  never makes a network call.

:meth:`screen` is the synchronous heuristic-only path; :meth:`ascreen` adds the
optional LLM fallback; :meth:`enforce` / :meth:`aenforce` raise
:class:`~pirn_agents.security.injection_detected_error.InjectionDetectedError`
on a flag so a caller can block-or-quarantine per policy.
"""

from __future__ import annotations

from collections.abc import Sequence
from re import Pattern

from pirn_agents._safe_pattern_compiler import SafePatternCompiler
from pirn_agents.security.injection_detected_error import InjectionDetectedError
from pirn_agents.security.injection_verdict import InjectionVerdict
from pirn_agents.security.llm_injection_classifier import LlmInjectionClassifier
from pirn_agents.security.untrusted_content import UntrustedContent


class InjectionScreen:
    """Heuristic-first injection gate with an optional budgeted LLM fallback."""

    def __init__(
        self,
        *,
        patterns: Sequence[str] | None = None,
        classifier: LlmInjectionClassifier | None = None,
        llm_budget: int = 0,
        flag_threshold: float = 0.5,
        ambiguous_threshold: float = 0.25,
    ) -> None:
        """Configure the heuristic patterns, optional classifier, and thresholds.

        Args:
            patterns: Optional override for the default injection regex set.
            classifier: Optional LLM fallback consulted only for ambiguous
                content within budget.
            llm_budget: Maximum number of LLM classifier calls this screen may
                make (``0`` disables the LLM tier entirely).
            flag_threshold: Heuristic score at/above which content is flagged
                outright.
            ambiguous_threshold: Lower bound of the grey zone; scores in
                ``[ambiguous_threshold, flag_threshold)`` are eligible for the
                LLM tier.

        Raises:
            TypeError: If ``classifier`` is set but not an
                :class:`LlmInjectionClassifier`.
            ValueError: If ``llm_budget`` is negative, a threshold is outside
                ``[0, 1]``, or ``ambiguous_threshold > flag_threshold``, or a
                pattern is invalid.
        """
        if classifier is not None and not isinstance(classifier, LlmInjectionClassifier):
            raise TypeError("InjectionScreen: classifier must be an LlmInjectionClassifier or None")
        if llm_budget < 0:
            raise ValueError("InjectionScreen: llm_budget must be >= 0")
        for label, value in (
            ("flag_threshold", flag_threshold),
            ("ambiguous_threshold", ambiguous_threshold),
        ):
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"InjectionScreen: {label} must be in [0, 1]")
        if ambiguous_threshold > flag_threshold:
            raise ValueError("InjectionScreen: ambiguous_threshold must be <= flag_threshold")
        self._pattern_compiler = SafePatternCompiler()
        raw = list(patterns) if patterns is not None else self._defaults()
        self._patterns: tuple[Pattern[str], ...] = tuple(
            self._pattern_compiler.compile_safe_pattern(
                p, index=i, owner="InjectionScreen", field="patterns"
            )
            for i, p in enumerate(raw)
        )
        self._classifier = classifier
        self._llm_calls_remaining = llm_budget
        self._flag_threshold = float(flag_threshold)
        self._ambiguous_threshold = float(ambiguous_threshold)

    @property
    def llm_calls_remaining(self) -> int:
        """Return how many LLM classifier calls this screen may still make."""
        return self._llm_calls_remaining

    @staticmethod
    def _defaults() -> list[str]:
        """Return the default indirect-injection heuristic patterns."""
        return [
            r"(?i)ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions",
            r"(?i)disregard\s+(?:the\s+)?(?:above|previous|system|prior)",
            r"(?i)forget\s+(?:everything|all\s+previous|your\s+instructions)",
            r"(?i)you\s+are\s+now\s+(?:a|an|in|no\s+longer)\b",
            r"(?i)new\s+(?:system\s+)?(?:instructions?|rules?|prompt)\s*:",
            r"(?i)\b(?:call|invoke|run|use|execute)\s+the\s+[\w.-]+\s+tool\b",
            r"(?i)system\s*prompt\b",
            r"(?i)reveal\s+(?:your\s+)?(?:system\s+prompt|instructions?|secrets?)",
            r"(?i)(?:exfiltrate|leak|send)\s+.{0,40}?(?:https?://|api[_-]?key|password|secret)",
            r"(?i)!\[[^\]]*\]\(https?://",
            r"(?i)override\s+(?:the\s+)?(?:system|instructions?|policy|guardrails?)",
        ]

    def screen(self, content: UntrustedContent | str) -> InjectionVerdict:
        """Return a heuristic-only verdict for ``content`` (no round-trip).

        Args:
            content: The untrusted content (or raw string) to screen.

        Returns:
            An :class:`InjectionVerdict` decided by the heuristic tier.

        Raises:
            TypeError: If ``content`` is of an unsupported type.
        """
        text = self._text_of(content)
        matched = self._match(text)
        score = self._score(matched)
        if score >= self._flag_threshold:
            return InjectionVerdict(
                flagged=True,
                score=score,
                decided_by="heuristic",
                reason=f"{len(matched)} injection pattern(s) matched",
                matched=matched,
            )
        return InjectionVerdict(
            flagged=False,
            score=score,
            decided_by="clean" if score == 0.0 else "heuristic",
            reason="no injection pattern crossed the flag threshold",
            matched=matched,
        )

    async def ascreen(self, content: UntrustedContent | str) -> InjectionVerdict:
        """Return a verdict, escalating ambiguous content to the LLM tier.

        The LLM classifier is consulted only when the heuristic score lands in
        ``[ambiguous_threshold, flag_threshold)``, a classifier is wired, and
        the budget is not exhausted; otherwise the heuristic verdict stands.
        """
        verdict = self.screen(content)
        if verdict.flagged or self._classifier is None or self._llm_calls_remaining <= 0:
            return verdict
        if verdict.score < self._ambiguous_threshold:
            return verdict
        self._llm_calls_remaining -= 1
        return await self._classifier.classify(self._text_of(content))

    def enforce(self, content: UntrustedContent | str) -> InjectionVerdict:
        """Screen ``content`` heuristically and raise if flagged.

        Returns:
            The (non-flagged) verdict when the content passes.

        Raises:
            InjectionDetectedError: If the verdict is flagged.
        """
        verdict = self.screen(content)
        if verdict.flagged:
            raise InjectionDetectedError(verdict)
        return verdict

    async def aenforce(self, content: UntrustedContent | str) -> InjectionVerdict:
        """Async :meth:`enforce`, using the optional LLM tier for ambiguity."""
        verdict = await self.ascreen(content)
        if verdict.flagged:
            raise InjectionDetectedError(verdict)
        return verdict

    def _match(self, text: str) -> tuple[str, ...]:
        """Return the distinct heuristic snippets matched in ``text``."""
        found: list[str] = []
        for pattern in self._patterns:
            hit = pattern.search(text)
            if hit is not None:
                found.append(hit.group(0).strip())
        return tuple(found)

    def _score(self, matched: tuple[str, ...]) -> float:
        """Map the number of matched patterns to a score in ``[0, 1]``."""
        if not matched:
            return 0.0
        # A single match lands in the ambiguous grey zone (eligible for the LLM
        # tier); two or more independent signals cross the flag threshold.
        return min(1.0, 0.3 * len(matched))

    @staticmethod
    def _text_of(content: UntrustedContent | str) -> str:
        """Return the raw payload text of ``content``."""
        if isinstance(content, UntrustedContent):
            return content.payload
        if isinstance(content, str):
            return content
        raise TypeError(
            f"InjectionScreen: content must be UntrustedContent or str, "
            f"got {type(content).__name__}"
        )
