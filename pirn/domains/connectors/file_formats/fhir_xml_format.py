"""``FhirXmlFormat`` — FHIR XML Bundle batch encoder/decoder.

Same semantics as :class:`FhirJsonFormat` but operates on FHIR XML bundles.
``defusedxml`` is used for safe parsing; ``lxml`` for serialisation.

PHI safety
----------
The same PHI fields stripped by :class:`FhirJsonFormat` are stripped here:
``name``, ``birthDate``, ``address``, ``telecom``, ``identifier``.
``identifier`` is hashed with SHA-256 and emitted as ``identifier_hash``.

Install: ``pip install pirn[health]``.
"""

from __future__ import annotations

import hashlib
import io
from collections.abc import Iterable, Mapping
from typing import Any, ClassVar

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class FhirXmlFormat(BatchFileFormat):
    """Whole-file FHIR XML Bundle encoder/decoder.

    PHI fields (``name``, ``birthDate``, ``address``, ``telecom``,
    ``identifier``) are stripped from the emitted ``data`` dict.
    ``identifier`` is hashed with SHA-256 and emitted as
    ``identifier_hash``.
    """

    _fhir_ns: ClassVar[str] = "http://hl7.org/fhir"
    _phi_keywords: ClassVar[frozenset[str]] = frozenset(
        {
            "name",
            "birthDate",
            "address",
            "telecom",
            "identifier",
        }
    )

    @property
    def name(self) -> str:
        return "fhir_xml"

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        self._load_fhir()
        defusedxml = self._load_defusedxml()
        tree = defusedxml.ElementTree.parse(io.BytesIO(payload))
        root = tree.getroot()
        records: list[dict[str, Any]] = []
        local_tag = self._local(root.tag)
        if local_tag == "Bundle":
            for entry_el in root.findall(f"{{{FhirXmlFormat._fhir_ns}}}entry"):
                resource_el = entry_el.find(f"{{{FhirXmlFormat._fhir_ns}}}resource")
                if resource_el is None:
                    continue
                children = list(resource_el)
                if not children:
                    continue
                actual = children[0]
                records.append(self._element_to_record(actual))
        else:
            records.append(self._element_to_record(root))
        return records

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        self._load_fhir()
        lxml_etree = self._load_lxml()
        materialised = [dict(r) for r in records]
        nsmap = {None: FhirXmlFormat._fhir_ns}
        bundle_el = lxml_etree.Element(f"{{{FhirXmlFormat._fhir_ns}}}Bundle", nsmap=nsmap)
        lxml_etree.SubElement(bundle_el, f"{{{FhirXmlFormat._fhir_ns}}}type").set(
            "value", "collection"
        )
        for record in materialised:
            entry_el = lxml_etree.SubElement(bundle_el, f"{{{FhirXmlFormat._fhir_ns}}}entry")
            resource_wrapper = lxml_etree.SubElement(
                entry_el, f"{{{FhirXmlFormat._fhir_ns}}}resource"
            )
            if "resource_type" not in record:
                raise KeyError(
                    "FhirXmlFormat: record missing required field 'resource_type'; "
                    f"got: {list(record)}"
                )
            resource_type = record["resource_type"]
            self._validate_xml_ncname(str(resource_type))
            res_el = lxml_etree.SubElement(
                resource_wrapper, f"{{{FhirXmlFormat._fhir_ns}}}{resource_type}"
            )
            if record.get("resource_id"):
                id_el = lxml_etree.SubElement(res_el, f"{{{FhirXmlFormat._fhir_ns}}}id")
                id_el.set("value", str(record["resource_id"]))
            if record.get("status"):
                st_el = lxml_etree.SubElement(res_el, f"{{{FhirXmlFormat._fhir_ns}}}status")
                st_el.set("value", str(record["status"]))
            data = record.get("data", {})
            for key, value in data.items():
                if key in ("resourceType", "id", "status", "identifier_hash"):
                    continue
                self._validate_xml_ncname(str(key))
                child_el = lxml_etree.SubElement(res_el, f"{{{FhirXmlFormat._fhir_ns}}}{key}")
                child_el.set("value", str(value) if value is not None else "")
        return lxml_etree.tostring(
            bundle_el,
            xml_declaration=True,
            encoding="UTF-8",
            pretty_print=True,
        )

    @classmethod
    def _element_to_record(cls, element: Any) -> dict[str, Any]:
        resource_type = cls._local(element.tag)
        resource_id = None
        status = None
        identifier_raw = None
        data: dict[str, Any] = {"resourceType": resource_type}
        for child in element:
            local = cls._local(child.tag)
            if local == "id":
                resource_id = child.get("value") or child.text
                data["id"] = resource_id
                continue
            if local == "status":
                status = child.get("value") or child.text
                data["status"] = status
                continue
            if local in cls._phi_keywords:
                if local == "identifier":
                    identifier_raw = child.get("value") or child.text or ""
                continue
            val = child.get("value") or child.text or ""
            data[local] = val
        if identifier_raw is not None:
            data["identifier_hash"] = hashlib.sha256(
                str(identifier_raw).encode("utf-8")
            ).hexdigest()
        return {
            "resource_type": resource_type,
            "resource_id": resource_id,
            "status": status,
            "data": data,
        }

    @staticmethod
    def _validate_xml_ncname(name: str) -> None:
        """Raise ValueError if *name* is not a valid XML NCName."""
        import re

        if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9._\-]*", name):
            raise ValueError(
                f"FhirXmlFormat: value {name!r} is not a valid XML element "
                "name (NCName). Must start with a letter or underscore and "
                "contain only alphanumerics, '.', '-', '_'."
            )

    @staticmethod
    def _local(tag: str) -> str:
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    @staticmethod
    def _load_fhir() -> Any:
        try:
            import fhir.resources
        except ImportError as exc:
            raise ImportError(
                "FhirXmlFormat requires fhir.resources. Install with `pip install pirn[health]`."
            ) from exc
        return fhir.resources

    @staticmethod
    def _load_defusedxml() -> Any:
        try:
            import defusedxml.ElementTree
        except ImportError as exc:
            raise ImportError(
                "FhirXmlFormat requires defusedxml. Install with `pip install pirn[health]`."
            ) from exc
        return defusedxml

    @staticmethod
    def _load_lxml() -> Any:
        try:
            from lxml import etree  # type: ignore[attr-defined]
        except ImportError as exc:
            raise ImportError(
                "FhirXmlFormat requires lxml. Install with `pip install pirn[health]`."
            ) from exc
        return etree
