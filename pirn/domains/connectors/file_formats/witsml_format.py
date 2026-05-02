"""``WitsmlFormat`` — WITSML XML drilling-data batch encoder/decoder.

WITSML (Wellsite Information Transfer Standard Markup Language) is an
XML-based standard for exchanging drilling and well operations data.

One record is emitted per ``<log>`` or ``<well>`` top-level element as a
flat ``dict[str, str]`` of ``{tag: text}`` pairs.

Writing reconstructs a minimal WITSML 1.4.1 XML document.

Uses ``defusedxml`` for safe parsing and ``lxml.etree`` for writing.

Install: ``pip install pirn[oilgas]``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)

_WITSML_NS = "http://www.witsml.org/schemas/1series"
_WITSML_VERSION = "1.4.1.1"


class WitsmlFormat(BatchFileFormat):
    """Whole-file WITSML encoder/decoder."""

    @property
    def name(self) -> str:
        return "witsml"

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        defusedxml = self._load_defusedxml()
        import io

        tree = defusedxml.ElementTree.parse(io.BytesIO(payload))
        root = tree.getroot()
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

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        lxml_etree = self._load_lxml()
        materialised = [dict(r) for r in records]
        root = lxml_etree.Element(
            "wellLogs",
            attrib={"version": _WITSML_VERSION},
            nsmap={None: _WITSML_NS},
        )
        for record in materialised:
            item_el = lxml_etree.SubElement(root, "wellLog")
            for key, value in record.items():
                child = lxml_etree.SubElement(item_el, str(key))
                child.text = str(value) if value is not None else ""
        return lxml_etree.tostring(
            root,
            xml_declaration=True,
            encoding="UTF-8",
            pretty_print=True,
        )

    @classmethod
    def _element_to_flat_dict(cls, element: Any) -> dict[str, Any]:
        """Flatten an XML element's children into a dict.

        Direct children with text content are emitted as ``{tag: text}``.
        Grandchildren are emitted as ``{child_tag.grandchild_tag: text}``.
        The element's own tag is not included as a key.
        """
        result: dict[str, Any] = {}
        for child in element:
            child_tag = cls._strip_ns(child.tag)
            if child.text and child.text.strip():
                result[child_tag] = child.text.strip()
            for grandchild in child:
                gc_tag = cls._strip_ns(grandchild.tag)
                if grandchild.text and grandchild.text.strip():
                    result[f"{child_tag}.{gc_tag}"] = (
                        grandchild.text.strip()
                    )
        # If element has no children but has direct text, use tag as key.
        if not result and element.text and element.text.strip():
            result[cls._strip_ns(element.tag)] = element.text.strip()
        return result

    @staticmethod
    def _strip_ns(tag: str) -> str:
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    @staticmethod
    def _load_defusedxml() -> Any:
        try:
            import defusedxml.ElementTree
        except ImportError as exc:
            raise ImportError(
                "WitsmlFormat requires defusedxml. Install with "
                "`pip install pirn[oilgas]`."
            ) from exc
        return defusedxml

    @staticmethod
    def _load_lxml() -> Any:
        try:
            from lxml import etree
        except ImportError as exc:
            raise ImportError(
                "WitsmlFormat requires lxml. Install with "
                "`pip install pirn[oilgas]`."
            ) from exc
        return etree
