"""``BrainVisionFormat`` — BrainVision EEG batch encoder/decoder.

BrainVision is a three-file EEG format:

* ``.vhdr`` — text header (INI-style)
* ``.vmrk`` — markers/events (INI-style)
* ``.eeg``  — raw binary signal data

The "payload" is a :mod:`zipfile` bundle containing all three files.
Decoding requires ``mne``, which applies each channel's ``Resolution``
factor and unit so records carry volts; there is deliberately no
header-only second decoder to silently substitute raw ADC integers for
them.

PHI safety
----------
``.vhdr`` headers may contain subject metadata under the keys
``SubjectName``, ``SubjectID``, and ``InstitutionName``. These are
stripped from decoded records and replaced with ``"[REDACTED]"`` on
encode.

Record shape (one per channel)::

    {
        "channel_index": int,
        "channel_name":  str,
        "sample_rate":   float,
        "n_samples":     int,
        "data":          bytes,  # raw float64 array bytes
    }

Install: ``pip install "pirn-health[health]"`` — required to decode.
"""

from __future__ import annotations

import io
import tempfile
import zipfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, ClassVar

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.core.optional_dependency import OptionalDependency

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray


class BrainVisionFormat(BatchFileFormat):
    """BrainVision (.vhdr/.vmrk/.eeg) encoder/decoder.

    The payload is a zip archive containing the three constituent files.
    Reading requires ``mne`` (``pip install "pirn-health[health]"``).
    """

    _phi_header_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "SubjectName",
            "SubjectID",
            "InstitutionName",
        }
    )

    @property
    def name(self) -> str:
        return "brainvision"

    # ------------------------------------------------------------------
    # Decode
    # ------------------------------------------------------------------

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        """Decode the zip bundle with ``mne``, or raise its install hint.

        There is no second decoder. ``mne`` returns channel data in volts,
        having applied each channel's ``Resolution`` factor and unit; a
        header-only parser returns raw ADC integers. Substituting one for the
        other when the import fails would make the same file decode to
        different numbers depending on what happens to be installed, with
        nothing in the records to say which happened (PIR-873).
        """
        bundle = self._unpack_zip(payload)
        mne = OptionalDependency.require("mne", extra="health", package="pirn-health")
        return self._decode_with_mne(mne, bundle)

    @classmethod
    def _decode_with_mne(cls, mne: ModuleType, bundle: dict[str, bytes]) -> list[Mapping[str, Any]]:
        import numpy as np

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "recording"
            vhdr_path = base.with_suffix(".vhdr")
            vmrk_path = base.with_suffix(".vmrk")
            eeg_path = base.with_suffix(".eeg")

            vhdr_bytes = bundle.get("recording.vhdr", b"")
            vmrk_bytes = bundle.get("recording.vmrk", b"")
            eeg_bytes = bundle.get("recording.eeg", b"")

            # Rewrite internal path references so mne can locate the files.
            vhdr_text = cls._rewrite_vhdr_paths(
                vhdr_bytes.decode("utf-8", errors="replace"), tmpdir
            )
            vhdr_path.write_text(vhdr_text, encoding="utf-8")
            vmrk_path.write_bytes(vmrk_bytes)
            eeg_path.write_bytes(eeg_bytes)

            raw = mne.io.read_raw_brainvision(str(vhdr_path), preload=True, verbose=False)
            data: NDArray[np.float64]
            data, _times = raw.get_data(return_times=True)
            sfreq: float = raw.info["sfreq"]
            ch_names: list[str] = raw.info["ch_names"]

            records: list[Mapping[str, Any]] = []
            for idx, ch_name in enumerate(ch_names):
                records.append(
                    {
                        "channel_index": idx,
                        "channel_name": ch_name,
                        "sample_rate": float(sfreq),
                        "n_samples": data.shape[1],
                        "data": data[idx].astype(np.float64).tobytes(),
                    }
                )
        return records

    # ------------------------------------------------------------------
    # Encode
    # ------------------------------------------------------------------

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        import numpy as np

        materialised = [dict(r) for r in records]
        if not materialised:
            raise ValueError(
                "BrainVisionFormat: cannot encode empty record stream — "
                "at least one channel record is required."
            )

        sfreq = float(materialised[0].get("sample_rate", 1000.0))
        ch_names = [str(r.get("channel_name", f"Ch{r['channel_index'] + 1}")) for r in materialised]

        # Build data matrix (channels x samples)
        arrays: list[NDArray[np.float64]] = []
        for rec in materialised:
            data_bytes = rec.get("data", b"")
            arr = np.frombuffer(data_bytes, dtype=np.float64)
            arrays.append(arr)
        n_samples = max((len(a) for a in arrays), default=0)
        # Pad/truncate to uniform length
        padded: list[NDArray[np.float64]] = []
        for arr in arrays:
            if len(arr) < n_samples:
                arr = np.pad(arr, (0, n_samples - len(arr)))
            else:
                arr = arr[:n_samples]
            padded.append(arr)

        data_matrix = np.stack(padded, axis=0)  # (n_channels, n_samples)
        # Interleaved binary (MULTIPLEXED = sample x channel)
        eeg_bytes = data_matrix.T.astype(np.float32).tobytes()

        vhdr_text = self._build_vhdr(ch_names, sfreq, n_samples)
        vmrk_text = self._build_vmrk()

        bundle: dict[str, bytes] = {
            "recording.vhdr": vhdr_text.encode("utf-8"),
            "recording.vmrk": vmrk_text.encode("utf-8"),
            "recording.eeg": eeg_bytes,
        }
        return self._pack_zip(bundle)

    # ------------------------------------------------------------------
    # Zip helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _unpack_zip(payload: bytes) -> dict[str, bytes]:
        bundle: dict[str, bytes] = {}
        with zipfile.ZipFile(io.BytesIO(payload), "r") as zf:
            for name in zf.namelist():
                bundle[name] = zf.read(name)
        return bundle

    @staticmethod
    def _pack_zip(bundle: dict[str, bytes]) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in bundle.items():
                zf.writestr(name, data)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # VHDR / VMRK builders
    # ------------------------------------------------------------------

    @classmethod
    def _build_vhdr(cls, ch_names: list[str], sfreq: float, n_samples: int) -> str:
        sampling_interval = int(1_000_000 / sfreq)
        lines = [
            "Brain Vision Data Exchange Header File Version 1.0",
            "",
            "[Common Infos]",
            "Codepage=UTF-8",
            "DataFile=recording.eeg",
            "MarkerFile=recording.vmrk",
            "DataFormat=BINARY",
            "DataOrientation=MULTIPLEXED",
            f"NumberOfChannels={len(ch_names)}",
            f"SamplingInterval={sampling_interval}",
            "",
            "[Binary Infos]",
            "BinaryFormat=IEEE_FLOAT_32",
            "",
            "[Channel Infos]",
        ]
        for idx, name in enumerate(ch_names):
            # Redact PHI fields if present in channel name (unlikely but
            # consistent with the class-level policy).
            safe_name = "[REDACTED]" if name in cls._phi_header_fields else name
            lines.append(f"Ch{idx + 1}={safe_name},,1,µV")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _build_vmrk() -> str:
        return (
            "Brain Vision Data Exchange Marker File, Version 1.0\n"
            "\n"
            "[Common Infos]\n"
            "Codepage=UTF-8\n"
            "DataFile=recording.eeg\n"
            "\n"
            "[Marker Infos]\n"
        )

    @classmethod
    def _rewrite_vhdr_paths(cls, vhdr_text: str, tmpdir: str) -> str:
        """Rewrite DataFile/MarkerFile paths to point to tmpdir."""
        lines: list[str] = []
        for line in vhdr_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("DataFile="):
                lines.append("DataFile=recording.eeg")
            elif stripped.startswith("MarkerFile="):
                lines.append("MarkerFile=recording.vmrk")
            else:
                lines.append(line)
        return "\n".join(lines)
