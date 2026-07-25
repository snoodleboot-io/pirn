"""``ContentBlock`` — base type for one typed unit of message content (F15-S1).

A message body is a *sequence* of content blocks — text, image, audio, file, or
an embedded tool result — rather than a single string. Every concrete block is a
frozen :class:`pirn.core.pirn_opaque_value.PirnOpaqueValue`, so blocks travel the
pirn graph opaquely and content-address by their audit form (never by raw media
bytes, which stay out of lineage — see
:class:`pirn_agents.types.media_handle.MediaHandle`).

This base declares only the two projections every block shares:

* :attr:`modality` — a neutral wire-independent tag (``"text"``, ``"image"``,
  ``"audio"``, ``"file"``, ``"tool_result"``) used for capability gating and
  provider encoding.
* :attr:`as_text` — the plain-text projection of the block (its own text, an
  ``alt``/``transcript`` caption, or ``""``) so a text-only consumer can always
  degrade a multimodal message to a string without special-casing each variant.
"""

from __future__ import annotations

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class ContentBlock(PirnOpaqueValue):
    """One typed unit of message content; base of the content-block union."""

    @property
    def modality(self) -> str:
        """Return the neutral modality tag for this block.

        Raises:
            NotImplementedError: Always, in the base; every concrete block
                overrides this with its own tag.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement modality")

    @property
    def as_text(self) -> str:
        """Return the plain-text projection of this block.

        The base returns ``""`` so non-text blocks contribute nothing to a
        text-only rendering; :class:`~pirn_agents.types.text_block.TextBlock`
        returns its text and media blocks return any caption they carry.
        """
        return ""
