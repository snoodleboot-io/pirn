from __future__ import annotations

from typing import Literal

from pydantic import Field

from pirn.yaml_loader.specs.node_spec import NodeSpec


class AggregatorSpec(NodeSpec):
    type: Literal["aggregator"]
    combine: str = Field(..., description="Dotted path to the combine callable.  Loose mode required.")
    parents: dict[str, str] = Field(default_factory=dict)
