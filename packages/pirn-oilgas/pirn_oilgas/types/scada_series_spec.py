"""``ScadaSeriesSpec`` — declarative description of one SCADA rate series.

Bundles the per-series inputs (``label``, ``rows``, ``tag``) that a workflow
assembling several :class:`~pirn_oilgas.assemblers.scada_database_assembler.
ScadaDatabaseAssembler` instances would otherwise repeat as parallel
positional keyword groups (``oil_rows``/``oil_tag``, ``gas_rows``/
``gas_tag``, ...). ``since`` and ``sample_interval_sec`` are shared across
every series in a workflow and are not part of this spec.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ScadaSeriesSpec(BaseModel):
    """One SCADA historian series: a role label, its raw rows, and its tag.

    Attributes:
        label: Non-empty role name for this series (e.g. ``"oil"``,
            ``"gas"``, ``"water"``). Used to key the series and to build a
            readable per-series ``KnotConfig`` id.
        rows: Historian query rows for this series — a list of
            ``(timestamp, value)`` tuples.
        tag: Non-empty SCADA tag name for this series.
    """

    model_config = ConfigDict(frozen=True)

    label: str
    rows: list[tuple[Any, ...]]
    tag: str
