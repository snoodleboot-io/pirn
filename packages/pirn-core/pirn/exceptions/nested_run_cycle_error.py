"""Raised when a container knot re-enters itself through nested runs."""

from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class NestedRunCycleError(PirnError):
    """A container knot is already on the nested-run path it is joining.

    A ``SubTapestry`` whose inner pipeline reaches — however indirectly —
    the same container again (its class and knot id, see
    ``SubTapestry._nesting_key``) recurses until it hits the depth cap.
    With a cap active the frame refuses the re-entry at once instead, naming
    the container and the path, so the recursion is diagnosed where it starts.
    Raised inside the re-entering container, so the enclosing engine records
    it as that knot's ``Err``.

    Attributes:
        key: Nesting key (qualified class name and knot id) of the re-entering container.
        path: Nesting keys already on the path, outermost first.
    """

    def __init__(self, *, key: str, path: tuple[str, ...]) -> None:
        super().__init__(
            f"container {key!r} is already on the nested-run path {list(path)!r}; "
            "a nested run re-entering its own container is a cycle"
        )
        self.key = key
        self.path = path
