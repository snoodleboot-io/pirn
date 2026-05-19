from __future__ import annotations

import re
from typing import TYPE_CHECKING, Annotated, Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pirn.core.error_policy import ErrorPolicy

if TYPE_CHECKING:
    pass


class KnotConfig(BaseModel):
    """Framework configuration attached to a single knot instance.

    Users supply this via the reserved ``_config=`` keyword argument when
    constructing a knot.  All fields except ``id`` have sensible defaults so
    callers only set what they need to override.

    Knot ids are required and must be supplied explicitly.  Auto-generated ids
    produce lineage records that are hard to read and impossible to query
    reliably across runs; explicit ids keep lineage human-readable and stable.

    Attributes:
        id: Stable, unique identifier for the knot.  Allowed characters:
            alphanumeric, underscore, hyphen, dot, colon.  Max 256 characters.
            Required; no default is generated.
        validate_io: When ``True`` (default), inputs and outputs are validated
            against the ``process()`` signature using Pydantic
            ``TypeAdapter``\\s at each invocation.  Set ``False`` only in
            performance-critical hot paths where types are already guaranteed.
        error_policy: Controls how the scheduler reacts when this knot's
            upstream parents fail or are skipped.  Defaults to
            ``ErrorPolicy.SKIP_IF_PARENT_FAILED``.
        description: Optional human-readable description surfaced in
            visualisations and generated documentation.
        tags: Free-form string tags used for grouping and filtering in
            visualisations.
        transport: Per-knot ``DataTransport`` override.  When set, the engine
            uses this transport for writing this knot's output instead of the
            tapestry-level default.  ``None`` means "inherit from the
            tapestry".  Excluded from ``model_dump`` so it does not appear in
            lineage hashes.
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
    def validate_id_characters(cls, id_value: str) -> str:
        if not cls._knot_id_re.match(id_value):
            raise ValueError(
                f"knot id {id_value!r} contains invalid characters. "
                "Allowed: alphanumeric, underscore, hyphen, dot, colon. Max length: 256. "
                "Null bytes, path separators, whitespace, and control characters are not permitted."
            )
        return id_value

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
