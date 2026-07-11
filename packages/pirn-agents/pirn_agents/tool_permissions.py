"""``ToolPermissions`` — per-tool permission / scope metadata.

A :class:`ToolPermissions` is an immutable value object attached to a tool
that describes *how* the tool may be called: the OAuth-style ``scope`` it
requires, whether it mutates state or is read-only, whether a human must
approve each call, and a relative ``cost_hint`` a planner can use to prefer
cheaper tools.

The default instance is **unrestricted and inert**: no scope, non-mutating,
no approval required, no cost hint. It is a deliberate forward hook for the
security (F11) and human-in-the-loop (F14) surfaces — those features read this
metadata to gate execution; until they land the metadata is descriptive only
and changes no behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ToolPermissions(PirnOpaqueValue):
    """Immutable permission / scope metadata for a single tool.

    Attributes
    ----------
    scope:
        OAuth-style scope string the caller must hold to invoke the tool.
        ``None`` means no scope is required.
    mutating:
        ``True`` when the tool changes external state (write/delete);
        ``False`` (default) marks a read-only tool.
    approval_required:
        ``True`` when each call must be approved by a human before it runs.
        Routed through the F11/F14 approval seam; ``False`` (default) runs
        unattended.
    cost_hint:
        Optional non-negative relative cost a planner may use to prefer
        cheaper tools. ``None`` means unspecified.
    """

    scope: str | None = None
    mutating: bool = False
    approval_required: bool = False
    cost_hint: float | None = None

    def __post_init__(self) -> None:
        """Validate field types and the ``cost_hint`` domain.

        Raises
        ------
        TypeError
            If any field has the wrong type.
        ValueError
            If ``cost_hint`` is negative.
        """
        if self.scope is not None and not isinstance(self.scope, str):
            raise TypeError(f"scope must be a str or None, got {type(self.scope).__name__}")
        if not isinstance(self.mutating, bool):
            raise TypeError(f"mutating must be a bool, got {type(self.mutating).__name__}")
        if not isinstance(self.approval_required, bool):
            raise TypeError(
                f"approval_required must be a bool, got {type(self.approval_required).__name__}"
            )
        if self.cost_hint is not None:
            if isinstance(self.cost_hint, bool) or not isinstance(self.cost_hint, (int, float)):
                raise TypeError(
                    f"cost_hint must be a number or None, got {type(self.cost_hint).__name__}"
                )
            if self.cost_hint < 0:
                raise ValueError(f"cost_hint must be non-negative, got {self.cost_hint}")

    @property
    def is_default(self) -> bool:
        """Return whether this is the unrestricted, inert default."""
        return (
            self.scope is None
            and self.mutating is False
            and self.approval_required is False
            and self.cost_hint is None
        )

    def as_schema_fragment(self) -> dict[str, Any]:
        """Return a JSON-friendly dict of the non-default fields.

        Only fields that differ from the unrestricted default appear, so an
        unrestricted tool contributes an empty fragment.
        """
        fragment: dict[str, Any] = {}
        if self.scope is not None:
            fragment["scope"] = self.scope
        if self.mutating:
            fragment["mutating"] = True
        if self.approval_required:
            fragment["approval_required"] = True
        if self.cost_hint is not None:
            fragment["cost_hint"] = self.cost_hint
        return fragment

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Return a stable content-addressing view of the metadata."""
        return {
            "scope": self.scope,
            "mutating": self.mutating,
            "approval_required": self.approval_required,
            "cost_hint": self.cost_hint,
        }
