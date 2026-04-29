from __future__ import annotations

from typing import Literal

from pydantic import Field

from pirn.yaml_loader.specs.node_spec import NodeSpec


class BranchSpec(NodeSpec):
    type: Literal["branch"]
    input: str = Field(..., description="Knot id of the input.")
    selector: str = Field(..., description="Dotted path to the selector callable.")
    branches: list[str] = Field(..., min_length=1)
