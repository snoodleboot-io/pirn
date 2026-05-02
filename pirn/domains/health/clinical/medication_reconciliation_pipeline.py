"""``MedicationReconciliationPipeline`` — ingest → normalise → dedup pipeline.

Composed pipeline: :class:`RxNormNormalizer` resolves drug names to
RxCUI, then a final dedup step collapses duplicates. The pipeline is
expressed as a :class:`SubTapestry` so its inner graph is visible to
the engine and can be cached / replayed independently.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_result import RunResult
from pirn.domains.health.clinical._dedup_rx_cuis import _DedupRxCUIs
from pirn.domains.health.clinical.rxnorm_normalizer import RxNormNormalizer
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class MedicationReconciliationPipeline(SubTapestry):
    """Normalise a list of drug names and emit a deduplicated RxCUI tuple."""

    def __init__(
        self,
        *,
        drug_names: Sequence[str],
        mapping: Mapping[str, str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(drug_names, (list, tuple)):
            raise TypeError(
                "MedicationReconciliationPipeline: drug_names must be list/tuple"
            )
        if not isinstance(mapping, Mapping):
            raise TypeError(
                "MedicationReconciliationPipeline: mapping must be a Mapping"
            )
        self._drug_names = tuple(drug_names)
        self._mapping = dict(mapping)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> RunResult:
        with Tapestry() as inner:
            normalised = RxNormNormalizer(
                drug_names=self._drug_names,
                mapping=self._mapping,
                _config=KnotConfig(id="rxnorm-normalize"),
            )
            _DedupRxCUIs(
                rxcuis=normalised,
                _config=KnotConfig(id="rxnorm-dedup"),
            )
        return await self._run_inner(inner)
