"""``FHIRPatientIngestor`` — pull Patient resources from a FHIR server.

Production version would call ``fhir.resources`` / ``fhirclient`` to
materialise full Patient resources. This stub keeps the orchestration
contract: it consumes a :class:`FHIRClient` plus a search predicate
mapping and returns a tuple of :class:`ClinicalRecord`. The stub body
returns an empty tuple so downstream knots see a well-typed input
without a live FHIR endpoint.

Algorithm:
    1. Receive a FHIRClient and a search_params mapping.
    2. Validate that client is a FHIRClient and search_params is a Mapping.
    3. Search the FHIR server for Patient resources matching the params.
    4. Convert each FHIR Patient resource to a ClinicalRecord.
    5. Return the tuple of ClinicalRecords.


References:
    - HL7 FHIR R4 Patient: https://hl7.org/fhir/R4/patient.html
    - fhirclient: https://github.com/smart-on-fhir/client-py
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.protocols.fhir_client import FHIRClient
from pirn.domains.health.types.clinical_record import ClinicalRecord


class FHIRPatientIngestor(Knot):
    """Stream patients matching ``search_params`` from a FHIR server."""

    def __init__(
        self,
        *,
        client: Knot | FHIRClient,
        search_params: Knot | Mapping[str, Any],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            client=client,
            search_params=search_params,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        client: FHIRClient,
        search_params: Mapping[str, Any],
        **_: Any,
    ) -> tuple[ClinicalRecord, ...]:
        """Search the FHIR server for Patient resources matching the search params and return ClinicalRecords.

        Args:
            client: FHIRClient instance for querying the FHIR server.
            search_params: Mapping of FHIR search parameter names to values.

        Returns:
            A tuple of ClinicalRecords corresponding to the matching FHIR Patient resources.

        Raises:
            TypeError: If client is not a FHIRClient or search_params is not a Mapping.
        """
        if not isinstance(client, FHIRClient):
            raise TypeError(
                "FHIRPatientIngestor: client must be a FHIRClient"
            )
        if not isinstance(search_params, Mapping):
            raise TypeError(
                "FHIRPatientIngestor: search_params must be a Mapping"
            )
        # Production: iterate ``client.search('Patient', params)`` and
        # convert each FHIR Patient resource into a ClinicalRecord.
        return ()
