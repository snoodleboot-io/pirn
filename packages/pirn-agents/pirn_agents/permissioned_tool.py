"""``PermissionedTool`` — structural contract for tools carrying permissions.

A tool "carries permissions" when it exposes a
:class:`~pirn_agents.tool_permissions.ToolPermissions` value under a
``permissions`` attribute. :class:`PermissionedTool` is a
:func:`~typing.runtime_checkable` :class:`~typing.Protocol` capturing that
shape, so callers can detect and read a tool's permission metadata without the
tool having to inherit from any base class.

The module-level :func:`requires_approval` predicate is the single place the
rest of the codebase asks "must this call be approved?"; it keeps the
permission-reading logic in one spot so the F11/F14 approval seam stays inert
for tools that expose no permissions.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pirn_agents.tool_permissions import ToolPermissions


@runtime_checkable
class PermissionedTool(Protocol):
    """A tool that exposes :class:`ToolPermissions` under ``permissions``."""

    @property
    def permissions(self) -> ToolPermissions:
        """Return the permission / scope metadata for this tool."""
        ...


def permissions_of(tool: object) -> ToolPermissions:
    """Return a tool's :class:`ToolPermissions`, or the inert default.

    Tools that do not expose ``permissions`` are treated as unrestricted,
    which keeps permission-aware call sites backward-compatible with plain
    :class:`~pirn_agents.tool.Tool` implementations.
    """
    if isinstance(tool, PermissionedTool):
        return tool.permissions
    return ToolPermissions()


def requires_approval(tool: object) -> bool:
    """Return whether invoking ``tool`` requires human approval."""
    return permissions_of(tool).approval_required
