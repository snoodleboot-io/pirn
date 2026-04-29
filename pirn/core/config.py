"""Knot configuration — framework metadata for a knot instance.

Users pass a ``KnotConfig`` via the reserved ``_config=`` kwarg when
constructing a knot.  Everything in here is framework-level concern: the
knot's id, validation policy, error-handling policy, etc.  User-defined
knot inputs / parameters never collide because they go through normal
kwargs (parents and config values).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ErrorPolicy(StrEnum):
    """How a knot reacts when one or more parents produced ``Err``/``Skipped``.

    * ``SKIP_IF_PARENT_FAILED`` — if any parent failed or was skipped, this
      knot is skipped.  The default.
    * ``RECEIVE_ERRORS`` — the knot's ``process`` is called with the parents'
      ``Result`` values directly; the author is responsible for handling
      ``Err`` and ``Skipped`` cases.
    * ``REQUIRE_ALL_PARENTS`` — strict: any failed or skipped parent causes
      this knot itself to fail with a deterministic ``Err``.
    """

    SKIP_IF_PARENT_FAILED = "skip_if_parent_failed"
    RECEIVE_ERRORS = "receive_errors"
    REQUIRE_ALL_PARENTS = "require_all_parents"


class KnotConfig(BaseModel):
    """Framework configuration for a knot instance.

    Users pass this via the reserved ``_config=`` kwarg.  All fields have
    defaults; users only set what they want to override.

    The knot ``id`` is REQUIRED at construction.  We don't auto-generate
    ids — the user knows what to call their knots, and explicit ids make
    lineage records readable.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(
        ...,
        description="Stable identifier for this knot.  Required.",
        min_length=1,
    )
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
