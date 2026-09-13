"""Raised when a knot names a concurrency group the run's limits do not define."""

from __future__ import annotations

from collections.abc import Iterable

from pirn.exceptions.pirn_error import PirnError


class UndefinedConcurrencyGroupError(PirnError):
    """A knot's ``concurrency_group`` is not among the groups the limits define.

    Raised only when the run's ``ConcurrencyLimits`` define at least one
    group.  Admitting such a knot bounded by nothing but ``max_in_flight``
    would let a misspelt group -- ``"open_ai"`` for ``"openai"`` -- silently
    run every call at once, so the run fails instead.

    Attributes:
        knot_id: The knot that named the group.
        group: The group it named.
        defined_groups: The groups the limits define, sorted.
    """

    def __init__(self, knot_id: str, group: str, defined_groups: Iterable[str]) -> None:
        self.knot_id = knot_id
        self.group = group
        self.defined_groups: tuple[str, ...] = tuple(sorted(defined_groups))
        super().__init__(
            f"knot {knot_id!r} is in concurrency group {group!r}, which the run's "
            f"ConcurrencyLimits do not define; defined groups: {list(self.defined_groups)}. "
            "Fix the group name, add it to ConcurrencyLimits.groups, or run with "
            "limits that define no groups."
        )

    def __reduce__(
        self,
    ) -> tuple[type[UndefinedConcurrencyGroupError], tuple[str, str, tuple[str, ...]]]:
        # Exceptions pickle as cls(*args); args here is the message alone.
        return (type(self), (self.knot_id, self.group, self.defined_groups))
