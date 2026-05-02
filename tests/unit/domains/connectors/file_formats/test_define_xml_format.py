"""Tests for :class:`DefineXmlFormat` — CDISC Define-XML 2.x format."""

from __future__ import annotations

import pytest

pytest.importorskip("lxml")
pytest.importorskip("defusedxml")

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.define_xml_format import DefineXmlFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)

_ODM_NS = "http://www.cdisc.org/ns/odm/v1.3"


def _make_define_xml(items: list[dict]) -> bytes:
    item_defs = ""
    for item in items:
        length_attr = f' Length="{item["length"]}"' if item.get("length") else ""
        label_el = ""
        if item.get("label"):
            label_el = (
                f'<Description xmlns="{_ODM_NS}">'
                f'<TranslatedText xmlns="{_ODM_NS}">{item["label"]}</TranslatedText>'
                f"</Description>"
            )
        item_defs += (
            f'<ItemDef xmlns="{_ODM_NS}" '
            f'OID="{item["oid"]}" '
            f'Name="{item["name"]}" '
            f'DataType="{item["data_type"]}"'
            f'{length_attr}>'
            f"{label_el}"
            f"</ItemDef>"
        )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ODM xmlns="{_ODM_NS}" FileType="Snapshot" Granularity="Metadata">
  <Study OID="STUDY.1">
    <MetaDataVersion OID="MDV.1" Name="MetaDataVersion">
      {item_defs}
    </MetaDataVersion>
  </Study>
</ODM>
""".encode("utf-8")


async def _decode(fmt: DefineXmlFormat, payload: bytes) -> list[dict]:
    async def _iter():
        yield payload

    records = []
    async for rec in await fmt.read(_iter()):
        records.append(dict(rec))
    return records


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestDefineXmlFormatConstruction:
    def test_is_batch_format(self) -> None:
        assert isinstance(DefineXmlFormat(), BatchFileFormat)

    def test_streaming_false(self) -> None:
        assert DefineXmlFormat().streaming is False

    def test_name(self) -> None:
        assert DefineXmlFormat().name == "define_xml"


# ---------------------------------------------------------------------------
# PHI sanitisation (not applicable — Define-XML has no PHI)
# ---------------------------------------------------------------------------

class TestDefineXmlFormatNoPhiRequired:
    def test_no_phi_keywords_needed(self) -> None:
        """Define-XML contains no PHI; confirm class instantiates cleanly."""
        fmt = DefineXmlFormat()
        assert fmt.name == "define_xml"

    @pytest.mark.asyncio
    async def test_record_shape(self) -> None:
        payload = _make_define_xml(
            [{"oid": "IT.SUBJ", "name": "SUBJ", "data_type": "text", "length": 20, "label": "Subject ID"}]
        )
        records = await _decode(DefineXmlFormat(), payload)
        assert len(records) == 1
        record = records[0]
        assert "oid" in record
        assert "name" in record
        assert "data_type" in record
        assert "length" in record
        assert "label" in record

    @pytest.mark.asyncio
    async def test_fields_decoded_correctly(self) -> None:
        payload = _make_define_xml(
            [{"oid": "IT.AGE", "name": "AGE", "data_type": "integer", "length": 3, "label": "Age in years"}]
        )
        records = await _decode(DefineXmlFormat(), payload)
        assert records[0]["oid"] == "IT.AGE"
        assert records[0]["name"] == "AGE"
        assert records[0]["data_type"] == "integer"
        assert records[0]["length"] == 3
        assert records[0]["label"] == "Age in years"

    @pytest.mark.asyncio
    async def test_multiple_items(self) -> None:
        items = [
            {"oid": "IT.SUBJ", "name": "SUBJ", "data_type": "text", "length": 20, "label": "Subject"},
            {"oid": "IT.AGE", "name": "AGE", "data_type": "integer", "length": 3, "label": None},
            {"oid": "IT.SEX", "name": "SEX", "data_type": "text", "length": 1, "label": "Sex"},
        ]
        payload = _make_define_xml(items)
        records = await _decode(DefineXmlFormat(), payload)
        assert len(records) == 3
        oids = [r["oid"] for r in records]
        assert "IT.SUBJ" in oids
        assert "IT.AGE" in oids
        assert "IT.SEX" in oids


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

class TestDefineXmlFormatRoundTrip:
    @pytest.mark.asyncio
    async def test_round_trip_single_item(self) -> None:
        records = [
            {
                "oid": "IT.SUBJ",
                "name": "SUBJ",
                "data_type": "text",
                "length": 20,
                "label": "Subject ID",
            }
        ]
        fmt = DefineXmlFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        assert decoded[0]["oid"] == "IT.SUBJ"
        assert decoded[0]["name"] == "SUBJ"
        assert decoded[0]["data_type"] == "text"
        assert decoded[0]["length"] == 20
        assert decoded[0]["label"] == "Subject ID"

    @pytest.mark.asyncio
    async def test_round_trip_multiple_items(self) -> None:
        records = [
            {"oid": "IT.SUBJ", "name": "SUBJ", "data_type": "text", "length": 20, "label": "Subject"},
            {"oid": "IT.AGE", "name": "AGE", "data_type": "integer", "length": 3, "label": None},
        ]
        fmt = DefineXmlFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 2
        oids = [r["oid"] for r in decoded]
        assert "IT.SUBJ" in oids
        assert "IT.AGE" in oids


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

class TestDefineXmlFormatErrors:
    @pytest.mark.asyncio
    async def test_invalid_xml_raises(self) -> None:
        fmt = DefineXmlFormat()

        async def _iter():
            yield b"not xml <<<<"

        with pytest.raises(Exception):
            async for _ in await fmt.read(_iter()):
                pass


# ---------------------------------------------------------------------------
# Missing dependency
# ---------------------------------------------------------------------------

class TestDefineXmlFormatMissingDep:
    def test_missing_defusedxml_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sys
        monkeypatch.setitem(sys.modules, "defusedxml", None)  # type: ignore[arg-type]
        monkeypatch.setitem(sys.modules, "defusedxml.ElementTree", None)  # type: ignore[arg-type]
        fmt = DefineXmlFormat()
        with pytest.raises(ImportError, match="pirn\\[health\\]"):
            fmt._load_defusedxml()

    def test_missing_lxml_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sys
        monkeypatch.setitem(sys.modules, "lxml", None)  # type: ignore[arg-type]
        monkeypatch.setitem(sys.modules, "lxml.etree", None)  # type: ignore[arg-type]
        fmt = DefineXmlFormat()
        with pytest.raises(ImportError, match="pirn\\[health\\]"):
            fmt._load_lxml()
