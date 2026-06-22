"""``DefineXmlFormat`` — CDISC Define-XML 2.x batch encoder/decoder.

Define-XML is used for clinical trial dataset metadata submitted to
regulatory agencies. It contains no PHI — only structural metadata
describing dataset variables, their types, labels, and codelists.

One record is emitted per ``ItemDef`` element with shape::

    {
        "oid":       str,
        "name":      str,
        "data_type": str,
        "length":    int | None,
        "label":     str | None,
    }

Install: ``pip install pirn[health]``.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Mapping
from typing import Any, ClassVar

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class DefineXmlFormat(BatchFileFormat):
    """Whole-file CDISC Define-XML 2.x encoder/decoder.

    No PHI is present in Define-XML — it contains only structural
    metadata about clinical trial datasets.
    """

    _odm_ns: ClassVar[str] = "http://www.cdisc.org/ns/odm/v1.3"
    _def_ns: ClassVar[str] = "http://www.cdisc.org/ns/def/v2.0"

    @property
    def name(self) -> str:
        return "define_xml"

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        defusedxml = self._load_defusedxml()
        tree = defusedxml.ElementTree.parse(io.BytesIO(payload))
        root = tree.getroot()
        records: list[dict[str, Any]] = []
        for item_def in root.iter(f"{{{DefineXmlFormat._odm_ns}}}ItemDef"):
            records.append(self._item_def_to_record(item_def))
        return records

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        lxml_etree = self._load_lxml()
        materialised = [dict(r) for r in records]
        nsmap = {
            None: DefineXmlFormat._odm_ns,
            "def": DefineXmlFormat._def_ns,
        }
        root = lxml_etree.Element(
            f"{{{DefineXmlFormat._odm_ns}}}ODM",
            nsmap=nsmap,
        )
        root.set("FileType", "Snapshot")
        root.set("Granularity", "Metadata")
        study = lxml_etree.SubElement(root, f"{{{DefineXmlFormat._odm_ns}}}Study")
        study.set("OID", "STUDY.1")
        meta = lxml_etree.SubElement(study, f"{{{DefineXmlFormat._odm_ns}}}MetaDataVersion")
        meta.set("OID", "MDV.1")
        meta.set("Name", "MetaDataVersion")
        for record in materialised:
            item_def = lxml_etree.SubElement(meta, f"{{{DefineXmlFormat._odm_ns}}}ItemDef")
            item_def.set("OID", record.get("oid") or "")
            item_def.set("Name", record.get("name") or "")
            item_def.set("DataType", record.get("data_type") or "")
            length = record.get("length")
            if length is not None:
                item_def.set("Length", str(length))
            label = record.get("label")
            if label is not None:
                desc = lxml_etree.SubElement(item_def, f"{{{DefineXmlFormat._odm_ns}}}Description")
                trans = lxml_etree.SubElement(desc, f"{{{DefineXmlFormat._odm_ns}}}TranslatedText")
                trans.text = str(label)
        return lxml_etree.tostring(
            root,
            xml_declaration=True,
            encoding="UTF-8",
            pretty_print=True,
        )

    @classmethod
    def _item_def_to_record(cls, item_def: Any) -> dict[str, Any]:
        oid = item_def.get("OID") or ""
        name = item_def.get("Name") or ""
        data_type = item_def.get("DataType") or ""
        length_raw = item_def.get("Length")
        length: int | None = None
        if length_raw is not None:
            try:
                length = int(length_raw)
            except ValueError:
                length = None
        label: str | None = None
        desc_el = item_def.find(f"{{{DefineXmlFormat._odm_ns}}}Description")
        if desc_el is not None:
            trans_el = desc_el.find(f"{{{DefineXmlFormat._odm_ns}}}TranslatedText")
            if trans_el is not None and trans_el.text:
                label = trans_el.text.strip() or None
        return {
            "oid": oid,
            "name": name,
            "data_type": data_type,
            "length": length,
            "label": label,
        }

    @staticmethod
    def _load_defusedxml() -> Any:
        try:
            import defusedxml.ElementTree
        except ImportError as exc:
            raise ImportError(
                "DefineXmlFormat requires defusedxml. Install with `pip install pirn[health]`."
            ) from exc
        return defusedxml

    @staticmethod
    def _load_lxml() -> Any:
        try:
            from lxml import etree  # type: ignore[attr-defined]
        except ImportError as exc:
            raise ImportError(
                "DefineXmlFormat requires lxml. Install with `pip install pirn[health]`."
            ) from exc
        return etree
