# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``DefineXMLGenerator`` — emit a CDISC Define-XML metadata snippet.

Production version uses ``define-xml`` / ``odm-lib`` to build a
fully-validated Define-XML 2.x document. This stub emits a
deterministic XML snippet by string concatenation, sufficient for
downstream tooling that only inspects ``ItemGroupDef`` / ``ItemDef``
shape.

Algorithm:
    1. Validate dataset_name and variables mapping.
    2. Build an ItemGroupDef element with ItemDef children.
    3. Return the XML string.

References:
    - CDISC. (2021). Define-XML v2.1 Specification.

Note:
    ``_is_stub`` is ``True`` on this knot: it is a functional placeholder
    for the production implementation described above, not a complete
    algorithm. It is registered so pipelines can be wired and tested
    end-to-end before the real implementation lands; do not treat its
    output as production-quality.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class DefineXMLGenerator(Knot):
    """Produce a Define-XML ``ItemGroupDef`` snippet for a dataset."""

    _is_stub: ClassVar[bool] = True

    def __init__(
        self,
        *,
        dataset_name: Knot | str,
        variables: Knot | Mapping[str, Mapping[str, Any]],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(dataset_name=dataset_name, variables=variables, _config=_config, **kwargs)

    async def process(
        self,
        dataset_name: str,
        variables: Mapping[str, Mapping[str, Any]],
        **_: Any,
    ) -> str:
        """Build a Define-XML ItemGroupDef snippet for the dataset variables.

        Args:
            dataset_name: Non-empty name of the CDISC dataset.
            variables: Non-empty mapping of variable name to spec dict with 'type' and 'length'.

        Returns:
            String containing the ``ItemGroupDef`` element and its ``ItemDef`` children.

        Raises:
            ValueError: If dataset_name is empty, variables is empty, or specs lack required keys.
            TypeError: If variables is not a Mapping or a spec is not a Mapping.
        """
        if not isinstance(dataset_name, str) or not dataset_name:
            raise ValueError("DefineXMLGenerator: dataset_name must be a non-empty string")
        if not isinstance(variables, Mapping):
            raise TypeError("DefineXMLGenerator: variables must be a Mapping")
        if len(variables) == 0:
            raise ValueError("DefineXMLGenerator: variables must be non-empty")
        for var_name, spec in variables.items():
            if not isinstance(var_name, str) or not var_name:
                raise ValueError("DefineXMLGenerator: variable names must be non-empty strings")
            if not isinstance(spec, Mapping):
                raise TypeError(f"DefineXMLGenerator: variable {var_name!r} spec must be a Mapping")
            if "type" not in spec or "length" not in spec:
                raise ValueError(
                    f"DefineXMLGenerator: variable {var_name!r} spec must include 'type' and 'length'"
                )
        parts: list[str] = [f'<ItemGroupDef OID="IG.{dataset_name}" Name="{dataset_name}">']
        for var_name, spec in variables.items():
            parts.append(
                f'<ItemDef OID="IT.{dataset_name}.{var_name}" '
                f'Name="{var_name}" '
                f'DataType="{spec["type"]}" '
                f'Length="{spec["length"]}"/>'
            )
        parts.append("</ItemGroupDef>")
        return "".join(parts)
