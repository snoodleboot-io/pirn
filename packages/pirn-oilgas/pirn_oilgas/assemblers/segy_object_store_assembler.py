# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``SegyObjectStoreAssembler`` — assemble a :class:`SegyVolume` from raw SEG-Y bytes.

Sits between :class:`~pirn.connectors.knots.object_store_read_source.ObjectStoreReadSource`
(which produces ``bytes``) and downstream seismic knots that consume
:class:`~pirn_oilgas.types.segy_volume.SegyVolume`.

Algorithm:
    1. Receive ``body`` (raw SEG-Y bytes) and ``volume_id``.
    2. Validate types and values.
    3. Decode bytes via ``segyio`` on a thread to avoid blocking the event loop.
    4. Return a :class:`SegyVolume` carrying the inline/crossline/sample
       dimensions read from the binary file header.

Note:
    ``segyio`` has no in-memory reader — it only opens SEG-Y from a real
    filesystem path. Decoding therefore round-trips ``body`` through a
    ``NamedTemporaryFile`` before handing the path to ``segyio.open``. This is
    scratch I/O local to the decode step, not the connector I/O that
    ``docs/contributing/assembler-disassembler-pattern.md`` (Assembler
    Contract, item 5, "Perform no I/O") prohibits — no data crosses a
    connector boundary here, the bytes are already fully materialised in
    memory. The temp file is opened via a context manager with
    ``delete=True`` so it is always removed, including on exceptions.

References:
    - SEG Technical Standards Committee (2017). SEG-Y_r2.0 Data Exchange Format.
      Society of Exploration Geophysicists.
"""

from __future__ import annotations

import asyncio
import tempfile
from datetime import UTC, datetime
from typing import Any

from pirn.core.assembler import Assembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.optional_dependency import OptionalDependency

from pirn_oilgas.types.segy_volume import SegyVolume


class SegyObjectStoreAssembler(Assembler):
    """Assemble a :class:`SegyVolume` from raw SEG-Y bytes."""

    @staticmethod
    def _decode(body: bytes, volume_id: str) -> SegyVolume:
        segyio = OptionalDependency.require("segyio", extra="oilgas", package="pirn-oilgas")

        with tempfile.NamedTemporaryFile(suffix=".segy", delete=True) as segy_temp_file:
            segy_temp_file.write(body)
            segy_temp_file.flush()
            with segyio.open(segy_temp_file.name, "r", ignore_geometry=True) as segy_file:
                inline_count = (
                    len(segy_file.ilines)
                    if hasattr(segy_file, "ilines") and segy_file.ilines is not None
                    else 0
                )
                xline_count = (
                    len(segy_file.xlines)
                    if hasattr(segy_file, "xlines") and segy_file.xlines is not None
                    else 0
                )
                sample_count = int(segy_file.bin[segyio.BinField.Samples])
        return SegyVolume(
            volume_id=volume_id,
            inline_count=inline_count,
            xline_count=xline_count,
            sample_count=sample_count,
            fetched_at=datetime.now(UTC),
        )

    def __init__(
        self,
        *,
        body: Knot,
        volume_id: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(body=body, volume_id=volume_id, _config=_config, **kwargs)

    async def process(
        self,
        body: bytes,
        volume_id: str,
        **_: Any,
    ) -> SegyVolume:
        """Decode raw SEG-Y bytes into a :class:`SegyVolume`.

        Args:
            body: Raw SEG-Y file bytes from an object store or other connector.
            volume_id: Non-empty identifier for this seismic volume.

        Returns:
            :class:`SegyVolume` with dimension metadata decoded from ``body``.

        Raises:
            TypeError: If ``body`` is not ``bytes`` or ``volume_id`` is not ``str``.
            ValueError: If ``volume_id`` is empty.
        """
        if not isinstance(body, bytes):
            raise TypeError(
                f"SegyObjectStoreAssembler: body must be bytes, got {type(body).__name__}"
            )
        if not isinstance(volume_id, str):
            raise TypeError(
                f"SegyObjectStoreAssembler: volume_id must be str, got {type(volume_id).__name__}"
            )
        if not volume_id:
            raise ValueError("SegyObjectStoreAssembler: volume_id must be non-empty")
        return await asyncio.to_thread(SegyObjectStoreAssembler._decode, body, volume_id)
