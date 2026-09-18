"""``DicomRecord`` — one decoded DICOM file.

Part of the ``examples.domain_formats.medical_triage_agent`` example.
"""

from __future__ import annotations

import random
import struct
from dataclasses import dataclass


@dataclass(frozen=True)
class DicomRecord:
    """Matches the record schema emitted by ``DicomFormat.decode()``."""

    patient_id: str
    modality: str
    study_date: str
    series_number: int
    rows: int
    columns: int
    pixel_data: bytes
    metadata: dict[str, str]

    @staticmethod
    def synthetic_pixel_data(rows: int, cols: int, rng: random.Random) -> bytes:
        """Return ``rows * cols`` big-endian float32 samples of synthetic signal."""
        n = rows * cols
        values = [rng.gauss(0.0, 400.0) for _ in range(n)]
        return struct.pack(f">{n}f", *values)
