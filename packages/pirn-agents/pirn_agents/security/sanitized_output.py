"""``SanitizedOutput`` — the result of sanitizing one tool payload.

A frozen record of what
:class:`~pirn_agents.security.tool_output_sanitizer.ToolOutputSanitizer` produced
from a raw tool output: the cleaned ``text`` safe to re-enter the prompt, how
many control characters were ``stripped``, whether the payload was ``truncated``
at the size cap, the ``original_length``, and the tuple of
:class:`~pirn_agents.security.quarantined_item.QuarantinedItem`s pulled out.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.security.quarantined_item import QuarantinedItem


@dataclass(frozen=True)
class SanitizedOutput(PirnOpaqueValue):
    """Immutable outcome of sanitizing a tool output.

    Attributes
    ----------
    text:
        The sanitized text: control-stripped, size-capped, active content
        replaced with inert placeholders.
    original_length:
        Character length of the raw input before sanitization.
    truncated:
        ``True`` when the payload exceeded the size cap and was cut.
    stripped:
        Number of control characters / escape sequences removed.
    quarantined:
        The active-content spans removed from the payload.
    """

    text: str
    original_length: int
    truncated: bool
    stripped: int
    quarantined: tuple[QuarantinedItem, ...] = ()

    def __post_init__(self) -> None:
        """Validate the field types and numeric domains.

        Raises
        ------
        TypeError
            If a field has the wrong type.
        ValueError
            If ``original_length`` or ``stripped`` is negative.
        """
        if not isinstance(self.text, str):
            raise TypeError("SanitizedOutput: text must be a str")
        for label in ("original_length", "stripped"):
            value = getattr(self, label)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"SanitizedOutput: {label} must be an int")
            if value < 0:
                raise ValueError(f"SanitizedOutput: {label} must be non-negative")
        if not isinstance(self.truncated, bool):
            raise TypeError("SanitizedOutput: truncated must be a bool")

    @property
    def has_active_content(self) -> bool:
        """Return whether any active content was quarantined."""
        return bool(self.quarantined)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Return a stable content-addressing view of the outcome."""
        return {
            "text": self.text,
            "original_length": self.original_length,
            "truncated": self.truncated,
            "stripped": self.stripped,
            "quarantined": [item._pirn_audit_dict() for item in self.quarantined],
        }
