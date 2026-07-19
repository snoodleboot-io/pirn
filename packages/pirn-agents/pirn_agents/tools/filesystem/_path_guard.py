"""Path-traversal guard shared by the root-scoped filesystem tools.

:class:`PathGuard` binds to a single root directory (resolved once in the
constructor) and resolves caller-supplied *relative* paths against it, refusing
anything that could escape. It mirrors the hardening in
:class:`pirn_agents.specializations.document_processing._document_loader._DocumentLoader`:

* absolute inputs are rejected outright;
* ``..`` segments are rejected before resolution (belt and suspenders);
* every path component *under the root* is checked for being a symlink, so a
  symlink that points elsewhere cannot be used as a stepping stone;
* the fully-resolved path must remain inside the resolved root.

The guard never reads or writes; :meth:`resolve` only computes a vetted, absolute
:class:`~pathlib.Path` (or raises :class:`ValueError`), and :attr:`root` exposes
the resolved root for a tool's own in-root path arithmetic.
"""

from __future__ import annotations

from pathlib import Path

from pirn_agents.security.security_guard import SecurityGuard


class PathGuard(SecurityGuard):
    """Resolve relative paths against a fixed root and reject any escape."""

    def __init__(self, *, root: str) -> None:
        """Resolve ``root`` to an existing directory, raising on anything else.

        Args:
            root: The configured root directory path.

        Raises:
            ValueError: If ``root`` does not exist or is not a directory.
        """
        self._root: Path = self._resolve_root(root)

    @property
    def root(self) -> Path:
        """The strictly-resolved absolute root directory."""
        return self._root

    def resolve(self, relative: str, *, must_exist: bool) -> Path:
        """Resolve ``relative`` against the root and reject any escape attempt.

        Args:
            relative: The caller-supplied relative path; ``""`` denotes the root.
            must_exist: When ``True`` the target must already exist (reads/listing);
                when ``False`` only the *parent* must exist and be in-root (writes).

        Returns:
            The vetted, absolute path guaranteed to live inside the root.

        Raises:
            ValueError: If ``relative`` is absolute, contains ``..``, traverses a
                symlink, resolves outside the root, or (when ``must_exist``) does
                not exist.
        """
        rel_path = Path(relative)
        if rel_path.is_absolute():
            self._reject(f"filesystem: refusing absolute path {relative!r}")
        if ".." in rel_path.parts:
            self._reject(f"filesystem: refusing '..' traversal in {relative!r}")
        candidate = self._root / rel_path
        self._reject_symlink_components(candidate)
        if must_exist:
            try:
                resolved = candidate.resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                raise ValueError(f"filesystem: path does not exist: {relative!r}") from exc
        else:
            resolved = candidate.resolve()
            parent = resolved.parent
            if not parent.is_dir():
                self._reject(f"filesystem: parent directory does not exist: {relative!r}")
        if not resolved.is_relative_to(self._root):
            self._reject(f"filesystem: refusing to escape root with {relative!r}")
        return resolved

    @staticmethod
    def _resolve_root(root: str) -> Path:
        """Strictly resolve ``root``, requiring an existing directory."""
        try:
            resolved = Path(root).resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ValueError(f"filesystem: root does not exist: {root!r}") from exc
        if not resolved.is_dir():
            raise ValueError(f"filesystem: root is not a directory: {root!r}")
        return resolved

    def _reject_symlink_components(self, candidate: Path) -> None:
        """Raise if ``candidate`` or any component between it and the root is a symlink.

        Walks ``candidate`` and each of its ancestors, stopping at (and never
        inspecting) the root itself, so only components *inside* the root are
        vetted.
        """
        for component in (candidate, *candidate.parents):
            if component == self._root:
                return
            if component.is_symlink():
                self._reject(f"filesystem: refusing to traverse symlink: {component.name!r}")
