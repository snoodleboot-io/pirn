"""``ContentBlockHandler`` — interface for one content-block ``type`` handler.

The OCP seam behind :meth:`OutputParser._coerce_blocks`. Each concrete handler
recognises a single content-block ``type`` (``"text"``, ``"tool_use"``, …) and,
when it matches, returns a :class:`BlockContribution`; otherwise it returns
``None`` so the parser tries the next handler. Adding support for a new block
type is a new subclass added to the parser's handler tuple — no ``if/elif``
chain to edit.

Following the house interface style (never :class:`typing.Protocol`), this base
raises :class:`NotImplementedError` for :meth:`try_handle`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn_agents.generation.block_contribution import BlockContribution


class ContentBlockHandler:
    """Interface for one content-block ``type`` handler."""

    def try_handle(self, block: Mapping[str, Any]) -> BlockContribution | None:
        """Return this block's contribution, or ``None`` if unrecognised.

        Args:
            block: A single content-block mapping from the response.

        Returns:
            A :class:`BlockContribution` when this handler recognises the block,
            otherwise ``None`` to defer to the next handler.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement try_handle()")
