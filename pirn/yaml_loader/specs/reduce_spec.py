from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from pirn.yaml_loader.specs.node_spec import NodeSpec


class ReduceSpec(NodeSpec):
    type: Literal["reduce"]
    of: str = Field(..., description="Knot id producing the list.")
    combine: str
    initial: Any = None
    has_initial: bool = False
