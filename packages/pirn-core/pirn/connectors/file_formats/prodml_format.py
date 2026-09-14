"""``ProdmlFormat`` — PRODML XML production-data batch encoder/decoder.

PRODML (Production Markup Language) is an XML-based standard for
exchanging oil and gas production data defined by Energistics.

One record is emitted per top-level child element as a flat
``dict[str, str]`` of ``{tag: text}`` pairs.

Writing reconstructs a minimal PRODML XML document.

Uses ``defusedxml`` for safe parsing and ``lxml.etree`` for writing.

Install: ``pip install "pirn-oilgas[oilgas]"`` (``defusedxml``) and
``pip install "pirn-core[html]"`` (``lxml``).
"""

from __future__ import annotations

import io
import re
from collections.abc import Iterable, Mapping
from typing import Any, ClassVar
from xml.etree.ElementTree import Element

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.core.optional_dependency import OptionalDependency


class ProdmlFormat(BatchFileFormat):
    """Whole-file PRODML encoder/decoder."""

    _prodml_ns: ClassVar[str] = "http://www.prodml.org/schemas/1series"

    @property
    def name(self) -> str:
        return "prodml"

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        defused_element_tree = OptionalDependency.require(
            "defusedxml.ElementTree", extra="oilgas", package="pirn-oilgas"
        )
        root: Element = defused_element_tree.parse(io.BytesIO(payload)).getroot()
        records: list[dict[str, Any]] = []
        children = list(root)
        if children:
            for child in children:
                record = self._element_to_flat_dict(child)
                if record:
                    records.append(record)
        if not records:
            records.append(self._element_to_flat_dict(root))
        return records

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        lxml_etree = OptionalDependency.require("lxml.etree", extra="html")
        materialised = [dict(r) for r in records]
        root = lxml_etree.Element(
            "prodmlObjects",
            nsmap={None: self._prodml_ns},
        )
        for record in materialised:
            item_el = lxml_etree.SubElement(root, "prodmlObject")
            for key, value in record.items():
                self._validate_xml_ncname(str(key))
                child = lxml_etree.SubElement(item_el, str(key))
                child.text = str(value) if value is not None else ""
        serialised: bytes = lxml_etree.tostring(
            root,
            xml_declaration=True,
            encoding="UTF-8",
            pretty_print=True,
        )
        return serialised

    @classmethod
    def _element_to_flat_dict(cls, element: Element) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for child in element:
            child_tag = cls._strip_ns(child.tag)
            if child.text and child.text.strip():
                result[child_tag] = child.text.strip()
            for grandchild in child:
                gc_tag = cls._strip_ns(grandchild.tag)
                if grandchild.text and grandchild.text.strip():
                    result[f"{child_tag}.{gc_tag}"] = grandchild.text.strip()
        if not result and element.text and element.text.strip():
            result[cls._strip_ns(element.tag)] = element.text.strip()
        return result

    @staticmethod
    def _validate_xml_ncname(name: str) -> None:
        """Raise ValueError if *name* is not a valid XML NCName."""
        if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9._\-]*", name):
            raise ValueError(
                f"ProdmlFormat: record key {name!r} is not a valid XML "
                "element name (NCName). Keys must start with a letter or "
                "underscore and contain only alphanumerics, '.', '-', '_'."
            )

    @staticmethod
    def _strip_ns(tag: str) -> str:
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag
