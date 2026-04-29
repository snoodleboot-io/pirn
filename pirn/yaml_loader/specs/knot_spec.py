from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from pirn.yaml_loader.specs.node_spec import NodeSpec


class KnotSpec(NodeSpec):
    type: Literal["knot"]
    callable: str = Field(..., description="Dotted path to the function/Knot class.")
    parents: dict[str, str] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
