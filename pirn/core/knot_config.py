from __future__ import annotations

import re
from typing import TYPE_CHECKING, Annotated, Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pirn.core.error_policy import ErrorPolicy

if TYPE_CHECKING:
    pass


class KnotConfig(BaseModel):
    """Framework configuration for a knot instance.

    Users pass this via the reserved _config= kwarg.  All fields have
    defaults; users only set what they want to override.

    The knot id is REQUIRED at construction.  We don't auto-generate
    ids — the user knows what to call their knots, and explicit ids make
    lineage records readable.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    _knot_id_re: ClassVar[re.Pattern[str]] = re.compile(r"^[a-zA-Z0-9_\-\.:]{1,256}$")

    id: str = Field(
        ...,
        description="Stable identifier for this knot.  Required.",
        min_length=1,
    )

    @field_validator("id")
    @classmethod
    def validate_id_characters(cls, v: str) -> str:
        if not cls._knot_id_re.match(v):
            raise ValueError(
                f"knot id {v!r} contains invalid characters. "
                "Allowed: alphanumeric, underscore, hyphen, dot, colon. Max length: 256. "
                "Null bytes, path separators, whitespace, and control characters are not permitted."
            )
        return v

    validate_io: bool = Field(
        default=True,
        description="If True, inputs and outputs are validated against "
        "the process() signature using Pydantic TypeAdapters.",
    )
    error_policy: ErrorPolicy = Field(
        default=ErrorPolicy.SKIP_IF_PARENT_FAILED,
        description="How this knot reacts to upstream failures or skips.",
    )
    description: str | None = Field(
        default=None,
        description="Human-readable description for visualisation and docs.",
    )
    tags: tuple[str, ...] = Field(
        default=(),
        description="Free-form tags for grouping in visualisations.",
    )
    transport: Annotated[Any, Field(default=None, exclude=True)] = None
    """Per-knot transport override (Pass 2).

    When set, the engine uses this transport for writing this knot's output
    instead of the tapestry-level default.  The field is excluded from
    ``model_dump`` so it never appears in lineage hashes (which must remain
    stable regardless of which transport is in use).

    Pass an :class:`~pirn.core.transport.data_transport.DataTransport`
    instance; ``None`` means "inherit from the tapestry".
    """
