"""How many knots a run may have in flight, overall and per named group."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Annotated, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from pirn.core.concurrency.group_limits import GroupLimits


class ConcurrencyLimits(BaseModel):
    """Caps on how many knots of one run execute at the same time.

    The engine admits a ready knot only while both of its budgets have room:

    * ``max_in_flight`` -- every knot of the run counts against it;
    * ``groups[name]`` -- only knots whose ``KnotConfig.concurrency_group`` is
      ``name`` count against it.

    So ``ConcurrencyLimits(groups={"openai": 4})`` lets at most four OpenAI
    calls run at once while every other knot in the same run stays unbounded.
    With both set, the tighter of the two applies to a grouped knot.

    Undefined groups fail fast.  When these limits define *any* group, a knot
    whose ``concurrency_group`` is not one of them makes the run raise
    ``UndefinedConcurrencyGroupError`` -- at run start for the static graph,
    at admission for a knot registered mid-run -- because a typo such as
    ``"open_ai"`` for ``"openai"`` would otherwise silently lift the cap.
    When the limits define no groups, group tags are ignored, so a tapestry
    whose knots carry groups still runs under ``max_in_flight`` alone or
    unbounded.  A defined group that no knot of the static graph names only
    warns (``UnusedConcurrencyGroupWarning``): knots may still join it mid-run.

    Every field defaults to "no limit", so ``ConcurrencyLimits()`` is
    unbounded and behaves exactly as passing no limits at all.

    Known limitation (PIR-841 slice 2): a container knot -- ``SubTapestry``,
    ``LoopSubTapestry`` -- holds one slot for as long as its inner run lasts,
    and the inner run is not bound by these limits.  An open-ended
    ``LoopSubTapestry`` therefore occupies its slot for its whole life and,
    under a small ``max_in_flight``, can starve its siblings.  Slice 3 makes
    containers slot-free and forwards the limits into inner runs.

    Limits are a plain serialisable value: a trigger can decode them from a
    webhook body or queue message straight onto ``RunRequest.concurrency``.

    Limits govern scheduling only.  They never change a run's outputs, its
    lineage hashes, or the order its records are reported in.

    Attributes:
        max_in_flight: Most knots of the run in flight at once, or ``None``
            for no global limit.  At least 1.
        groups: Group name to the most knots of that group in flight at once.
            Each limit is at least 1.  Names follow the knot id charset.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    _group_name_re: ClassVar[re.Pattern[str]] = re.compile(r"^[a-zA-Z0-9_\-\.:]{1,256}$")

    max_in_flight: Annotated[int, Field(ge=1, strict=True)] | None = Field(
        default=None,
        description="Most knots of the run in flight at once; None means unbounded.",
    )
    groups: Mapping[str, Annotated[int, Field(ge=1, strict=True)]] = Field(
        default_factory=GroupLimits,
        description="Group name -> most knots of that group in flight at once.",
    )

    @classmethod
    def validate_group_name(cls, name: str) -> str:
        """Return *name* if it is a valid concurrency group name.

        Group names share the knot id charset -- alphanumeric, underscore,
        hyphen, dot, colon; 1 to 256 characters -- so a name that travels in
        JSON, a log line or a metric label never needs escaping.

        Args:
            name: The candidate group name.

        Returns:
            *name*, unchanged.

        Raises:
            ValueError: If *name* is empty, too long or has other characters.
        """
        if not cls._group_name_re.match(name):
            raise ValueError(
                f"concurrency group {name!r} contains invalid characters. "
                "Allowed: alphanumeric, underscore, hyphen, dot, colon. Max length: 256."
            )
        return name

    @field_validator("groups", mode="after")
    @classmethod
    def _freeze_groups(cls, groups: Mapping[str, int]) -> Mapping[str, int]:
        # Copy into a read-only mapping: a frozen value must not change because
        # the caller mutated the dict it was built from, or through ``groups``.
        # ``GroupLimits`` rather than ``MappingProxyType``, which cannot be
        # pickled or deep-copied and would make ``RunRequest`` unpicklable.
        for name in groups:
            cls.validate_group_name(name)
        return GroupLimits(groups)

    @field_serializer("groups")
    def _serialize_groups(self, groups: Mapping[str, int]) -> dict[str, int]:
        return dict(groups)

    @property
    def is_unbounded(self) -> bool:
        """Whether these limits constrain nothing at all."""
        return self.max_in_flight is None and not self.groups

    def group_limit(self, group: str | None) -> int | None:
        """Return the in-flight limit for *group*, or ``None`` if it has none.

        Args:
            group: A knot's ``concurrency_group``; ``None`` for an ungrouped
                knot, which never has a group limit.
        """
        if group is None:
            return None
        return self.groups.get(group)
