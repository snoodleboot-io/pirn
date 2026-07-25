"""``UntrustedContent`` — a delimited, provenance-tagged untrusted payload.

An :class:`UntrustedContent` is the frozen result of wrapping a raw tool / RAG /
MCP payload: it carries the original ``payload`` text, its
:class:`~pirn_agents.security.provenance_tag.ProvenanceTag`, and a precomputed
``rendered`` block that delimits and *spotlights* the payload so the model can
tell trusted instructions apart from untrusted data. The rendered form is
produced by :class:`~pirn_agents.security.untrusted_content_wrapper.UntrustedContentWrapper`,
which neutralises any attempt by the payload to forge the closing delimiter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.security.provenance_tag import ProvenanceTag


@dataclass(frozen=True)
class UntrustedContent(PirnOpaqueValue):
    """A wrapped, provenance-tagged untrusted payload ready for the prompt.

    Attributes
    ----------
    payload:
        The original untrusted text as produced by the source.
    provenance:
        The :class:`ProvenanceTag` describing where the payload came from.
    rendered:
        The delimited, spotlighted block safe to splice into the prompt.
    """

    payload: str
    provenance: ProvenanceTag
    rendered: str

    def __post_init__(self) -> None:
        """Validate the field types.

        Raises
        ------
        TypeError
            If ``payload`` / ``rendered`` are not strings or ``provenance`` is
            not a :class:`ProvenanceTag`.
        """
        if not isinstance(self.payload, str):
            raise TypeError(
                f"UntrustedContent: payload must be a str, got {type(self.payload).__name__}"
            )
        if not isinstance(self.provenance, ProvenanceTag):
            raise TypeError(
                f"UntrustedContent: provenance must be a ProvenanceTag, "
                f"got {type(self.provenance).__name__}"
            )
        if not isinstance(self.rendered, str):
            raise TypeError(
                f"UntrustedContent: rendered must be a str, got {type(self.rendered).__name__}"
            )

    def render(self) -> str:
        """Return the delimited, spotlighted block for prompt insertion."""
        return self.rendered

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Return a stable content-addressing view of the wrapped content."""
        return {
            "payload": self.payload,
            "provenance": self.provenance.to_payload(),
            "rendered": self.rendered,
        }
