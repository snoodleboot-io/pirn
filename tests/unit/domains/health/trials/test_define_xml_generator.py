"""Unit tests for :class:`DefineXMLGenerator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.trials.define_xml_generator import DefineXMLGenerator
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_dataset_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "dataset_name"):
            DefineXMLGenerator(
                dataset_name="",
                variables={"USUBJID": {"type": "text", "length": 32}},
                _config=KnotConfig(id="g"),
            )

    def test_rejects_empty_variables(self) -> None:
        with self.assertRaisesRegex(ValueError, "variables"):
            DefineXMLGenerator(
                dataset_name="ADSL",
                variables={},
                _config=KnotConfig(id="g"),
            )

    def test_rejects_non_mapping_variables(self) -> None:
        with self.assertRaisesRegex(TypeError, "variables"):
            DefineXMLGenerator(
                dataset_name="ADSL",
                variables=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="g"),
            )

    def test_rejects_variable_missing_type_or_length(self) -> None:
        with self.assertRaisesRegex(ValueError, "length"):
            DefineXMLGenerator(
                dataset_name="ADSL",
                variables={"USUBJID": {"type": "text"}},
                _config=KnotConfig(id="g"),
            )

    def test_rejects_non_mapping_variable_spec(self) -> None:
        with self.assertRaisesRegex(TypeError, "spec"):
            DefineXMLGenerator(
                dataset_name="ADSL",
                variables={"USUBJID": "not-a-mapping"},  # type: ignore[dict-item]
                _config=KnotConfig(id="g"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_item_group_def_snippet(self) -> None:
        with Tapestry() as t:
            DefineXMLGenerator(
                dataset_name="ADSL",
                variables={
                    "USUBJID": {"type": "text", "length": 32},
                    "AGE": {"type": "integer", "length": 8},
                },
                _config=KnotConfig(id="g"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["g"]
        assert isinstance(out, str)
        assert '<ItemGroupDef OID="IG.ADSL"' in out
        assert '<ItemDef OID="IT.ADSL.USUBJID"' in out
        assert '<ItemDef OID="IT.ADSL.AGE"' in out
        assert out.endswith("</ItemGroupDef>")
