"""``MudLogPayload`` — mud log metadata bundled with its decoded depth records.

``metadata`` carries the lineage metadata (well name, curve mnemonics, record
count). ``data`` is the tuple of depth records, each a mapping from curve
mnemonic to that record's value: a float for a measured curve (ROP, gas units,
depth) and a string for a described one (lithology, show description). Both
fields travel together through the transport layer, the same contract
:class:`~pirn_oilgas.types.las_payload.LASPayload` uses for well logs.
"""

from __future__ import annotations

from collections.abc import Mapping

from pirn.core.payload import Payload

from pirn_oilgas.types.mud_log import MudLog


class MudLogPayload(Payload[MudLog, tuple[Mapping[str, float | str], ...]]):
    """Mud log: metadata + decoded depth records."""
