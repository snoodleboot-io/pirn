"""``FhirJsonFormat`` — FHIR JSON Bundle batch encoder/decoder.

FHIR (Fast Healthcare Interoperability Resources) JSON bundles are the
dominant format for exchanging clinical resources between health systems.
This format decodes a FHIR Bundle JSON payload and emits one record per
resource entry, then reconstructs a Bundle on encode.

PHI safety
----------
FHIR resources carry Protected Health Information (PHI). ``FhirJsonFormat``
strips the following fields from the ``data`` dict in decoded records:

* ``name`` — patient name
* ``birthDate`` — date of birth
* ``address`` — postal address
* ``telecom`` — phone/email contact points
* ``identifier`` — raw patient identifier; replaced by ``identifier_hash``
  (SHA-256 hex digest)

Install: ``pip install pirn[health]``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any, ClassVar

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class FhirJsonFormat(BatchFileFormat):
    """Whole-file FHIR JSON Bundle encoder/decoder.

    PHI fields (``name``, ``birthDate``, ``address``, ``telecom``,
    ``identifier``) are stripped from the emitted ``data`` dict.
    ``identifier`` is hashed with SHA-256 and emitted as
    ``identifier_hash``.
    """

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
        return "fhir_json"

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        self._load_fhir()
        raw = json.loads(payload.decode("utf-8"))
        records: list[dict[str, Any]] = []
        entries = raw.get("entry", [])
        for entry in entries:
            resource = entry.get("resource", {})
            records.append(self._resource_to_record(resource))
        if not entries and raw.get("resourceType"):
            records.append(self._resource_to_record(raw))
        return records

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        self._load_fhir()
        materialised = [dict(r) for r in records]
        entries = []
        for record in materialised:
            resource = dict(record.get("data", {}))
            resource["resourceType"] = record.get("resource_type", "Resource")
            if record.get("resource_id"):
                resource["id"] = record["resource_id"]
            if record.get("status"):
                resource["status"] = record["status"]
            entries.append({"resource": resource})
        bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": entries,
        }
        return json.dumps(bundle, indent=2).encode("utf-8")

    @classmethod
    def _resource_to_record(cls, resource: dict[str, Any]) -> dict[str, Any]:
        resource_type = resource.get("resourceType", "")
        resource_id = resource.get("id")
        status = resource.get("status")
        data = {k: v for k, v in resource.items() if k not in cls._phi_keywords}
        identifier_raw = resource.get("identifier")
        if identifier_raw is not None:
            identifier_str = json.dumps(identifier_raw, sort_keys=True, default=str)
            data["identifier_hash"] = hashlib.sha256(identifier_str.encode("utf-8")).hexdigest()
        return {
            "resource_type": resource_type,
            "resource_id": resource_id,
            "status": status,
            "data": data,
        }

    @staticmethod
    def _load_fhir() -> Any:
        try:
            import fhir.resources
        except ImportError as exc:
            raise ImportError(
                "FhirJsonFormat requires fhir.resources. Install with `pip install pirn[health]`."
            ) from exc
        return fhir.resources
