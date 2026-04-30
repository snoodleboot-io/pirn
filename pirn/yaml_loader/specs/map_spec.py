from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from pirn.yaml_loader.specs.node_spec import NodeSpec


class MapSpec(NodeSpec):
    type: Literal["map"]
    over: str = Field(..., description="Knot id producing the collection.")
    each: str = Field(..., description="Dotted path to inner Knot class or @knot factory.")
    bind: str
    shared: dict[str, Any] = Field(default_factory=dict)
