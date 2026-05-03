"""``FHIRPatientIngestor`` — pull Patient resources from a FHIR server.

Production version would call ``fhir.resources`` / ``fhirclient`` to
materialise full Patient resources. This stub keeps the orchestration
contract: it consumes a :class:`FHIRClient` plus a search predicate
mapping and returns a tuple of :class:`ClinicalRecord`. The stub body
returns an empty tuple so downstream knots see a well-typed input
without a live FHIR endpoint.
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
        client: FHIRClient,
        search_params: Mapping[str, Any],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(client, FHIRClient):
            raise TypeError(
                "FHIRPatientIngestor: client must be a FHIRClient"
            )
        if not isinstance(search_params, Mapping):
            raise TypeError(
                "FHIRPatientIngestor: search_params must be a Mapping"
            )
        self._client = client
        self._search_params = dict(search_params)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> tuple[ClinicalRecord, ...]:
        """Search the FHIR server for Patient resources matching the search params and return ClinicalRecords.

        Returns:
            A tuple of ClinicalRecords corresponding to the matching FHIR Patient resources.
        """
        # Production: iterate ``self._client.search('Patient', params)`` and
        # convert each FHIR Patient resource into a ClinicalRecord.
        return ()
