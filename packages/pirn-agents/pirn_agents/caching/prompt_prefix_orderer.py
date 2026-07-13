"""``PromptPrefixOrderer`` — hoist stable content into a cacheable prompt prefix.

Provider prompt caches key on the *longest identical prefix* of a request, so
the way to maximise hits is to put everything that does not change between calls
(system prompt, tool schemas) first and everything that does (the user turn,
retrieved context) last — and to do so **deterministically**, byte-for-byte, so
the prefix is reused verbatim next time.

This orderer performs a *stable partition*: stable segments keep their relative
order and move ahead of the variable ones, which also keep their relative order.
Because only whole segments are reordered and their intra-group order is
preserved, the composed prompt carries the same information as the input — the
reordering never rewrites a segment or reshuffles the conversation. No backend is
touched; this is pure prompt shaping.
"""

from __future__ import annotations

from collections.abc import Sequence

from pirn_agents.caching.prompt_segment import PromptSegment


class PromptPrefixOrderer:
    """Reorder prompt segments so the stable, cacheable prefix always comes first."""

    def __init__(self, *, separator: str = "\n\n") -> None:
        """Create an orderer.

        Args:
            separator: Text joining rendered segment contents.

        Raises:
            TypeError: If ``separator`` is not a str.
        """
        if not isinstance(separator, str):
            raise TypeError(
                f"PromptPrefixOrderer: separator must be a str, got {type(separator).__name__}"
            )
        self._separator = separator

    def order(self, segments: Sequence[PromptSegment]) -> tuple[PromptSegment, ...]:
        """Return ``segments`` stable-partitioned: stable ones first, order preserved.

        Args:
            segments: The prompt segments in authoring order.

        Returns:
            The segments reordered so every stable segment precedes every
            variable one, with the original relative order kept within each group.

        Raises:
            TypeError: If any element is not a :class:`PromptSegment`.
        """
        validated = self._validate(segments)
        stable = [s for s in validated if s.stable]
        variable = [s for s in validated if not s.stable]
        return tuple(stable + variable)

    def stable_prefix(self, segments: Sequence[PromptSegment]) -> str:
        """Return the joined content of the leading stable segments only.

        This is the exact byte string a provider prompt cache should match on: it
        depends solely on the stable segments, so it is identical across calls
        whose variable content differs.
        """
        stable = [s.content for s in self._validate(segments) if s.stable]
        return self._separator.join(stable)

    def build(self, segments: Sequence[PromptSegment]) -> str:
        """Return the full prompt text with the stable prefix ordered first."""
        return self._separator.join(s.content for s in self.order(segments))

    @staticmethod
    def _validate(segments: Sequence[PromptSegment]) -> tuple[PromptSegment, ...]:
        """Return ``segments`` as a tuple, raising on any non-:class:`PromptSegment`."""
        out = tuple(segments)
        for index, segment in enumerate(out):
            if not isinstance(segment, PromptSegment):
                raise TypeError(
                    f"PromptPrefixOrderer: segments[{index}] must be a PromptSegment, got "
                    f"{type(segment).__name__}"
                )
        return out
