from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class NodeSpec(BaseModel):
    """Common fields for all node types."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    error_policy: str = "skip_if_parent_failed"
    validate_io: bool = True
