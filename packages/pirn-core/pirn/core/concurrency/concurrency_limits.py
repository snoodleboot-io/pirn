"""How many knots a run may have in flight, overall and per named group."""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class ConcurrencyLimits(BaseModel):
    """Caps on how many knots of one run execute at the same time.

    The engine admits a ready knot only while both of its budgets have room:

    * ``max_in_flight`` -- every knot of the run counts against it;
    * ``groups[name]`` -- only knots whose ``KnotConfig.concurrency_group`` is
      ``name`` count against it.

    So ``ConcurrencyLimits(groups={"openai": 4})`` lets at most four OpenAI
    calls run at once while every other knot in the same run stays unbounded.
    With both set, the tighter of the two applies to a grouped knot.

    A knot naming a group these limits do not list is bounded only by
    ``max_in_flight``; naming an unlisted group is not an error, so one graph
    can run under limits that care about some of its groups and not others.

    Every field defaults to "no limit", so ``ConcurrencyLimits()`` is
    unbounded and behaves exactly as passing no limits at all.

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
        default_factory=lambda: MappingProxyType({}),
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
        # Copy, then wrap read-only: a frozen value must not change because
        # the caller mutated the dict it was built from, or through ``groups``.
        for name in groups:
            cls.validate_group_name(name)
        return MappingProxyType(dict(groups))

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
