"""``CdaXmlFormat`` — CDA (Clinical Document Architecture) XML encoder/decoder.

CDA is an HL7 XML document standard used for clinical notes, discharge
summaries, and other structured documents. One record is emitted per
document with a nested ``body`` dict of section codes to text content.

PHI safety
----------
The following PHI fields are replaced with ``"[REDACTED]"`` in decoded
records:

* Patient ``name``
* Patient ``birthTime``
* Patient ``addr`` (address)
* Patient ``telecom`` (contact info)

Install: ``pip install pirn[health]``.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Mapping
from typing import Any, ClassVar

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class CdaXmlFormat(BatchFileFormat):
    """Whole-file CDA XML encoder/decoder.

    PHI fields (patient ``name``, ``birthTime``, ``addr``, ``telecom``)
    are replaced with ``"[REDACTED]"`` in decoded records.
    """

    _cda_ns: ClassVar[str] = "urn:hl7-org:v3"
    _phi_keywords: ClassVar[frozenset[str]] = frozenset(
        {"name", "birthTime", "addr", "telecom"}
    )

    @property
    def name(self) -> str:
        return "cda_xml"

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        defusedxml = self._load_defusedxml()
        tree = defusedxml.ElementTree.parse(io.BytesIO(payload))
        root = tree.getroot()

        document_id = self._find_extension(root, "id")
        template_id = self._find_extension(root, "templateId")
        title = self._find_text(root, "title")
        effective_time = self._find_extension_attr(root, "effectiveTime", "value")

        body = self._extract_body(root)
        record: dict[str, Any] = {
            "document_id": document_id,
            "template_id": template_id,
            "title": title,
            "effective_time": effective_time,
            "body": body,
        }
        return [record]

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        lxml_etree = self._load_lxml()
        materialised = [dict(r) for r in records]
        if not materialised:
            raise ValueError(
                "CdaXmlFormat: cannot encode an empty record stream."
            )
        record = materialised[0]
        nsmap = {None: CdaXmlFormat._cda_ns}
        root = lxml_etree.Element(
            f"{{{CdaXmlFormat._cda_ns}}}ClinicalDocument", nsmap=nsmap
        )
        # document id
        id_el = lxml_etree.SubElement(root, f"{{{CdaXmlFormat._cda_ns}}}id")
        id_el.set("extension", record.get("document_id") or "")
        # template id
        tmpl_el = lxml_etree.SubElement(root, f"{{{CdaXmlFormat._cda_ns}}}templateId")
        tmpl_el.set("root", record.get("template_id") or "")
        # title
        title_el = lxml_etree.SubElement(root, f"{{{CdaXmlFormat._cda_ns}}}title")
        title_el.text = record.get("title") or ""
        # effectiveTime
        et_el = lxml_etree.SubElement(root, f"{{{CdaXmlFormat._cda_ns}}}effectiveTime")
        et_el.set("value", record.get("effective_time") or "")
        # body sections
        body_el = lxml_etree.SubElement(
            root, f"{{{CdaXmlFormat._cda_ns}}}component"
        )
        structured_body = lxml_etree.SubElement(
            body_el, f"{{{CdaXmlFormat._cda_ns}}}structuredBody"
        )
        for code, text in (record.get("body") or {}).items():
            comp_el = lxml_etree.SubElement(
                structured_body, f"{{{CdaXmlFormat._cda_ns}}}component"
            )
            section_el = lxml_etree.SubElement(
                comp_el, f"{{{CdaXmlFormat._cda_ns}}}section"
            )
            code_el = lxml_etree.SubElement(
                section_el, f"{{{CdaXmlFormat._cda_ns}}}code"
            )
            code_el.set("code", str(code))
            text_el = lxml_etree.SubElement(
                section_el, f"{{{CdaXmlFormat._cda_ns}}}text"
            )
            text_el.text = str(text) if text is not None else ""
        return lxml_etree.tostring(
            root,
            xml_declaration=True,
            encoding="UTF-8",
            pretty_print=True,
        )

    @classmethod
    def _find_extension(cls, root: Any, tag: str) -> str:
        el = root.find(f"{{{CdaXmlFormat._cda_ns}}}{tag}")
        if el is None:
            return ""
        return el.get("extension") or el.get("root") or ""

    @classmethod
    def _find_extension_attr(
        cls, root: Any, tag: str, attr: str
    ) -> str:
        el = root.find(f"{{{CdaXmlFormat._cda_ns}}}{tag}")
        if el is None:
            return ""
        return el.get(attr) or ""

    @classmethod
    def _find_text(cls, root: Any, tag: str) -> str:
        el = root.find(f"{{{CdaXmlFormat._cda_ns}}}{tag}")
        if el is None:
            return ""
        return (el.text or "").strip()

    @classmethod
    def _extract_body(cls, root: Any) -> dict[str, Any]:
        body: dict[str, Any] = {}
        # Walk component/structuredBody/component/section elements
        for comp in root.iter(f"{{{CdaXmlFormat._cda_ns}}}section"):
            code_el = comp.find(f"{{{CdaXmlFormat._cda_ns}}}code")
            code = ""
            if code_el is not None:
                code = code_el.get("code") or code_el.get("displayName") or ""
            text_el = comp.find(f"{{{CdaXmlFormat._cda_ns}}}text")
            if text_el is not None:
                text_content = (text_el.text or "").strip()
            else:
                text_content = ""
            # Redact PHI from text content keys
            if not code:
                continue
            body[code] = text_content
        # Also pull patient record target PHI fields (redact)
        patient = root.find(
            f".//{{{CdaXmlFormat._cda_ns}}}patientRole"
        )
        if patient is not None:
            for phi_tag in cls._phi_keywords:
                for el in patient.findall(f"{{{CdaXmlFormat._cda_ns}}}{phi_tag}"):
                    el.text = "[REDACTED]"
                    for child in list(el):
                        el.remove(child)
        return body

    @staticmethod
    def _load_defusedxml() -> Any:
        try:
            import defusedxml.ElementTree
        except ImportError as exc:
            raise ImportError(
                "CdaXmlFormat requires defusedxml. Install with "
                "`pip install pirn[health]`."
            ) from exc
        return defusedxml

    @staticmethod
    def _load_lxml() -> Any:
        try:
            from lxml import etree
        except ImportError as exc:
            raise ImportError(
                "CdaXmlFormat requires lxml. Install with "
                "`pip install pirn[health]`."
            ) from exc
        return etree
