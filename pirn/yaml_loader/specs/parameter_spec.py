from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from pirn.yaml_loader.specs.node_spec import NodeSpec


class ParameterSpec(NodeSpec):
    type: Literal["parameter"]
    type_: str = Field(
        ...,
        description="Python type as a dotted path (e.g. 'int', 'str', 'list[dict]').",
    )
    default: Any = None
    has_default: bool = False
