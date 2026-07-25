"""``ChunkingStrategy`` — the pluggable chunking interface (F25-S2 / PIR-575).

Every named strategy (fixed-size, recursive-character, sentence-window,
semantic, parent-child, code-aware) implements this one contract: given a
document's text, return an ordered list of
:class:`~pirn_agents.specializations.document_processing.chunking.chunk.Chunk`.
This library is the *shared home* for chunking across the codebase — F9 indexing
patterns reuse these strategies rather than re-deriving splitting logic — so the
interface is provider-neutral and each strategy is independently testable.

The method is ``async`` because some strategies (semantic) call an embedding
provider; purely lexical strategies simply return synchronously.
"""

from __future__ import annotations

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.specializations.document_processing.chunking.chunk import Chunk


class ChunkingStrategy(PirnOpaqueValue):
    """Interface every chunking strategy satisfies: text → list of :class:`Chunk`."""

    async def chunk(self, text: str) -> list[Chunk]:
        """Split ``text`` into ordered chunks.

        Args:
            text: The document text to split.

        Returns:
            The ordered chunks; an empty list for empty input.

        Raises:
            NotImplementedError: Always, in the base class.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement chunk()")

    @staticmethod
    def _require_text(strategy_name: str, text: str) -> str:
        """Return ``text`` as ``str``, raising a clear ``TypeError`` otherwise."""
        if not isinstance(text, str):
            raise TypeError(f"{strategy_name}: text must be a string, got {type(text).__name__}")
        return text
