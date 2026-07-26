"""``NativeDecodeStrategy`` — interface for one capability-gated decode path.

The OCP seam behind :class:`StructuredDecoder`. Each concrete strategy owns a
single native, single-pass structured-output mechanism: it reports whether a
provider advertises its mechanism (:meth:`is_advertised`) and, when it does,
attempts a one-pass decode (:meth:`try_decode`). The decoder holds an ordered
tuple of these strategies and returns the first success, so adding a new
mechanism is a new subclass added to that tuple — no branch chain to edit.

Following the house interface style (never :class:`typing.Protocol`), this base
raises :class:`NotImplementedError` for both methods; subclasses override them.
"""

from __future__ import annotations

from pydantic import BaseModel

from pirn_agents.specializations.structured_output.structured_output_capability import (
    StructuredOutputCapability,
)
from pirn_agents.specializations.structured_output.structured_output_provider import (
    StructuredOutputProvider,
)


class NativeDecodeStrategy:
    """Interface for one capability-gated single-pass decode mechanism."""

    def is_advertised(self, capability: StructuredOutputCapability) -> bool:
        """Return whether ``capability`` advertises this strategy's mechanism.

        Args:
            capability: The provider's advertised structured-output flags.

        Returns:
            ``True`` when the provider advertises this strategy's mechanism.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement is_advertised()")

    async def try_decode(self, *, prompt: str, provider: StructuredOutputProvider) -> BaseModel:
        """Attempt a single-pass decode of ``prompt`` via this mechanism.

        Args:
            prompt: The prompt describing the data to produce.
            provider: A capability-advertising :class:`StructuredOutputProvider`.

        Returns:
            A validated model instance produced by this mechanism.

        Raises:
            StructuredDecodeError: If this mechanism cannot produce a valid
                instance, signalling the decoder to try the next strategy.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement try_decode()")
