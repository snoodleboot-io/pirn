from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Edge(BaseModel):
    """Wiring connection: parent_id feeds child_id at input name."""

    model_config = ConfigDict(frozen=True)

    child_id: str
    parent_id: str
    name: str
