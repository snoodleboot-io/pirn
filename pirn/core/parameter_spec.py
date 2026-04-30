"""ParameterSpec — declarative description of a pipeline parameter."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ParameterSpec(BaseModel):
    """Declarative description of a parameter.  Validated, serialisable."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    name: str
    type_: Any
    has_default: bool = False
    default: Any = None
    description: str | None = None
