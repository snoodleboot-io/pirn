"""Path-traversal guard shared by the root-scoped filesystem tools.

Every filesystem tool resolves a caller-supplied *relative* path against an
injected root directory and refuses anything that could escape it. The guard
mirrors the hardening in
:class:`pirn_agents.specializations.document_processing._document_loader._DocumentLoader`:

* absolute inputs are rejected outright;
* ``..`` segments are rejected before resolution (belt and suspenders);
* every path component *under the root* is checked for being a symlink, so a
  symlink that points elsewhere cannot be used as a stepping stone;
* the fully-resolved path must remain inside the resolved root.

The functions never read or write; they only compute a vetted, absolute
:class:`~pathlib.Path` (or raise :class:`ValueError`).
"""

from __future__ import annotations

from pathlib import Path


def resolve_root(root: str) -> Path:
    """Resolve ``root`` to an existing directory, raising on anything else.

    Args:
        root: The configured root directory path.

    Returns:
        The strictly-resolved absolute root :class:`~pathlib.Path`.

    Raises:
        ValueError: If ``root`` does not exist or is not a directory.
    """
    try:
        resolved = Path(root).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"filesystem: root does not exist: {root!r}") from exc
    if not resolved.is_dir():
        raise ValueError(f"filesystem: root is not a directory: {root!r}")
    return resolved


def resolve_in_root(root: Path, relative: str, *, must_exist: bool) -> Path:
    """Resolve ``relative`` against ``root`` and reject any escape attempt.

    Args:
        root: The already-resolved root directory (from :func:`resolve_root`).
        relative: The caller-supplied relative path; ``""`` denotes the root.
        must_exist: When ``True`` the target must already exist (reads/listing);
            when ``False`` only the *parent* must exist and be in-root (writes).

    Returns:
        The vetted, absolute path guaranteed to live inside ``root``.

    Raises:
        ValueError: If ``relative`` is absolute, contains ``..``, traverses a
            symlink, resolves outside ``root``, or (when ``must_exist``) does not
            exist.
    """
    rel_path = Path(relative)
    if rel_path.is_absolute():
        raise ValueError(f"filesystem: refusing absolute path {relative!r}")
    if ".." in rel_path.parts:
        raise ValueError(f"filesystem: refusing '..' traversal in {relative!r}")
    candidate = root / rel_path
    _reject_symlink_components(root, candidate)
    if must_exist:
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ValueError(f"filesystem: path does not exist: {relative!r}") from exc
    else:
        resolved = candidate.resolve()
        parent = resolved.parent
        if not parent.is_dir():
            raise ValueError(f"filesystem: parent directory does not exist: {relative!r}")
    if not resolved.is_relative_to(root):
        raise ValueError(f"filesystem: refusing to escape root with {relative!r}")
    return resolved


def _reject_symlink_components(root: Path, candidate: Path) -> None:
    """Raise if ``candidate`` or any component between it and ``root`` is a symlink.

    Walks ``candidate`` and each of its ancestors, stopping at (and never
    inspecting) ``root`` itself, so only components *inside* the root are vetted.
    """
    for component in (candidate, *candidate.parents):
        if component == root:
            return
        if component.is_symlink():
            raise ValueError(f"filesystem: refusing to traverse symlink: {component.name!r}")
