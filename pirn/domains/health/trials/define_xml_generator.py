"""``DefineXMLGenerator`` — emit a CDISC Define-XML metadata snippet.

Production version uses ``define-xml`` / ``odm-lib`` to build a
fully-validated Define-XML 2.x document. This stub emits a
deterministic XML snippet by string concatenation, sufficient for
downstream tooling that only inspects ``ItemGroupDef`` / ``ItemDef``
shape.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class DefineXMLGenerator(Knot):
    """Produce a Define-XML ``ItemGroupDef`` snippet for a dataset."""

    def __init__(
        self,
        *,
        dataset_name: str,
        variables: Mapping[str, Mapping[str, Any]],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(dataset_name, str) or not dataset_name:
            raise ValueError(
                "DefineXMLGenerator: dataset_name must be a non-empty string"
            )
        if not isinstance(variables, Mapping):
            raise TypeError(
                "DefineXMLGenerator: variables must be a Mapping"
            )
        if len(variables) == 0:
            raise ValueError(
                "DefineXMLGenerator: variables must be non-empty"
            )
        for var_name, spec in variables.items():
            if not isinstance(var_name, str) or not var_name:
                raise ValueError(
                    "DefineXMLGenerator: variable names must be non-empty strings"
                )
            if not isinstance(spec, Mapping):
                raise TypeError(
                    f"DefineXMLGenerator: variable {var_name!r} spec must be a Mapping"
                )
            if "type" not in spec or "length" not in spec:
                raise ValueError(
                    f"DefineXMLGenerator: variable {var_name!r} spec must "
                    "include 'type' and 'length'"
                )
        self._dataset_name = dataset_name
        self._variables = {
            name: dict(spec) for name, spec in variables.items()
        }
        super().__init__(_config=_config, **kwargs)

    @property
    def dataset_name(self) -> str:
        return self._dataset_name

    async def process(self, **_: Any) -> str:
        parts: list[str] = [
            f'<ItemGroupDef OID="IG.{self._dataset_name}" Name="{self._dataset_name}">'
        ]
        for var_name, spec in self._variables.items():
            parts.append(
                f'<ItemDef OID="IT.{self._dataset_name}.{var_name}" '
                f'Name="{var_name}" '
                f'DataType="{spec["type"]}" '
                f'Length="{spec["length"]}"/>'
            )
        parts.append("</ItemGroupDef>")
        return "".join(parts)
