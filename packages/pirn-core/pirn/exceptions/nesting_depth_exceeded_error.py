"""Raised when a nested run would go deeper than the path's ``max_nesting_depth``."""

from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class NestingDepthExceededError(PirnError):
    """Starting one more nested run would exceed the tightest cap on the path.

    Raised inside the container knot that tried to start the run, so the
    enclosing engine records it as that knot's ``Err``; the run that hit the
    cap never starts.

    Attributes:
        depth: The depth the refused run would have had.
        limit: The cap that refused it.
        path: Nesting keys of the container knots already on the path.
        key: Nesting key of the container that tried to go deeper, or
            ``None`` for a loop iteration.
    """

    def __init__(self, *, depth: int, limit: int, path: tuple[str, ...], key: str | None) -> None:
        where = f" by {key!r}" if key is not None else ""
        super().__init__(
            f"nested run{where} would reach depth {depth}, over max_nesting_depth={limit}; "
            f"path: {list(path)!r}"
        )
        self.depth = depth
        self.limit = limit
        self.path = path
        self.key = key
