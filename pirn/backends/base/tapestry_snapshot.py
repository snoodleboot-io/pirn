from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TapestrySnapshot(BaseModel):
    """An immutable view of a tapestry at a moment in time.

    Returned by TapestryStore.snapshot().  The engine takes a snapshot
    when planning a run so concurrent mutations to the store don't
    disturb the in-flight run.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    knot_ids: list[str] = Field(default_factory=list)
