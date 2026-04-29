from __future__ import annotations

import re
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pirn.core.error_policy import ErrorPolicy


class KnotConfig(BaseModel):
    """Framework configuration for a knot instance.

    Users pass this via the reserved _config= kwarg.  All fields have
    defaults; users only set what they want to override.

    The knot id is REQUIRED at construction.  We don't auto-generate
    ids — the user knows what to call their knots, and explicit ids make
    lineage records readable.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    _knot_id_re: ClassVar[re.Pattern[str]] = re.compile(r'^[a-zA-Z0-9_\-\.:]{1,256}$')

    id: str = Field(
        ...,
        description="Stable identifier for this knot.  Required.",
        min_length=1,
    )

    @field_validator('id')
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
