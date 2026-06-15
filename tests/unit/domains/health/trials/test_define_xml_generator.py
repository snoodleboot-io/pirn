"""Unit tests for :class:`DefineXMLGenerator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_health.trials.define_xml_generator import DefineXMLGenerator


def _make_knot(
    dataset_name: str = "ADSL",
    variables: object = None,
) -> DefineXMLGenerator:
    if variables is None:
        variables = {"USUBJID": {"type": "text", "length": 32}}
    with Tapestry():
        return DefineXMLGenerator(
            dataset_name=dataset_name,
            variables=variables,
            _config=KnotConfig(id="g"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_dataset_name(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "dataset_name"):
            await knot.process(
                dataset_name="",
                variables={"USUBJID": {"type": "text", "length": 32}},
            )

    async def test_rejects_empty_variables(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "variables"):
            await knot.process(dataset_name="ADSL", variables={})

    async def test_rejects_non_mapping_variable_spec(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(TypeError, "spec"):
            await knot.process(
                dataset_name="ADSL",
                variables={"USUBJID": "not-a-mapping"},  # type: ignore[dict-item]
            )

    async def test_rejects_variable_missing_type_or_length(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "length"):
            await knot.process(
                dataset_name="ADSL",
                variables={"USUBJID": {"type": "text"}},
            )

    async def test_emits_item_group_def_snippet(self) -> None:
        knot = _make_knot(
            variables={
                "USUBJID": {"type": "text", "length": 32},
                "AGE": {"type": "integer", "length": 8},
            }
        )
        out = await knot.process(
            dataset_name="ADSL",
            variables={
                "USUBJID": {"type": "text", "length": 32},
                "AGE": {"type": "integer", "length": 8},
            },
        )
        assert isinstance(out, str)
        assert '<ItemGroupDef OID="IG.ADSL"' in out
        assert '<ItemDef OID="IT.ADSL.USUBJID"' in out
        assert '<ItemDef OID="IT.ADSL.AGE"' in out
        assert out.endswith("</ItemGroupDef>")
