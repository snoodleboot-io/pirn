"""``QuarantinedItem`` — one piece of active content pulled out of tool output.

A frozen record of a script, embedded URL, ``javascript:`` / ``data:`` URI, or
inline event handler that
:class:`~pirn_agents.security.active_content_quarantine.ActiveContentQuarantine`
removed from a tool payload and replaced with an inert ``placeholder`` token, so
the model can see *that* active content existed without it being auto-followed
or executed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class QuarantinedItem(PirnOpaqueValue):
    """Immutable record of one quarantined active-content span.

    Attributes
    ----------
    kind:
        The active-content class: ``"script"``, ``"url"``, ``"javascript_uri"``,
        ``"data_uri"``, or ``"event_handler"``.
    value:
        The original active-content text that was removed.
    placeholder:
        The inert token that replaced ``value`` in the sanitized output.
    """

    kind: str
    value: str
    placeholder: str

    def __post_init__(self) -> None:
        """Validate the field types.

        Raises
        ------
        TypeError
            If any field is not a string.
        ValueError
            If ``kind`` is empty.
        """
        for label in ("kind", "value", "placeholder"):
            if not isinstance(getattr(self, label), str):
                raise TypeError(f"QuarantinedItem: {label} must be a str")
        if not self.kind:
            raise ValueError("QuarantinedItem: kind must be non-empty")

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Return a stable content-addressing view of the item."""
        return {"kind": self.kind, "value": self.value, "placeholder": self.placeholder}
