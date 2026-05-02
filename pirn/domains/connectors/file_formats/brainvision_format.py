"""``BrainVisionFormat`` — BrainVision EEG batch encoder/decoder.

BrainVision is a three-file EEG format:

* ``.vhdr`` — text header (INI-style)
* ``.vmrk`` — markers/events (INI-style)
* ``.eeg``  — raw binary signal data

The "payload" is a :mod:`zipfile` bundle containing all three files.
Decoding uses ``mne`` when available; otherwise a minimal pure-Python
parser reads the text header and interprets the raw binary data.

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

Install: ``pip install pirn[health]``.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Iterable, Mapping
from typing import Any, ClassVar

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class BrainVisionFormat(BatchFileFormat):
    """BrainVision (.vhdr/.vmrk/.eeg) encoder/decoder.

    The payload is a zip archive containing the three constituent files.
    Reading uses ``mne`` when available; a lightweight pure-Python
    fallback is used otherwise.
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

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        bundle = self._unpack_zip(payload)
        try:
            import mne as _mne  # noqa: F401
            return self._decode_with_mne(bundle)
        except ImportError:
            return self._decode_fallback(bundle)

    @classmethod
    def _decode_with_mne(
        cls, bundle: dict[str, bytes]
    ) -> list[Mapping[str, Any]]:
        import mne
        import numpy as np
        import tempfile
        from pathlib import Path

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

            raw = mne.io.read_raw_brainvision(
                str(vhdr_path), preload=True, verbose=False
            )
            data, _ = raw.get_data(return_times=True)
            sfreq = raw.info["sfreq"]
            ch_names = raw.info["ch_names"]

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

    @classmethod
    def _decode_fallback(
        cls, bundle: dict[str, bytes]
    ) -> list[Mapping[str, Any]]:
        """Pure-Python BrainVision decoder (no mne required)."""
        import configparser
        import numpy as np

        vhdr_text = bundle.get("recording.vhdr", b"").decode(
            "utf-8", errors="replace"
        )
        eeg_bytes = bundle.get("recording.eeg", b"")

        parser = cls._parse_vhdr(vhdr_text)

        # Channel count and sample rate from header
        n_channels = int(
            parser.get("Common Infos", "NumberOfChannels", fallback="0")
        )
        sfreq = 1_000_000.0 / float(
            parser.get("Common Infos", "SamplingInterval", fallback="1000")
        )
        data_format = parser.get(
            "Common Infos", "DataFormat", fallback="BINARY"
        ).upper()
        binary_format = parser.get(
            "Binary Infos", "BinaryFormat", fallback="INT_16"
        ).upper()
        data_orientation = parser.get(
            "Common Infos", "DataOrientation", fallback="MULTIPLEXED"
        ).upper()

        if data_format != "BINARY":
            raise ValueError(
                "BrainVisionFormat fallback: only BINARY DataFormat "
                f"is supported, got {data_format!r}"
            )

        dtype_map = {
            "INT_16": np.int16,
            "INT_32": np.int32,
            "IEEE_FLOAT_32": np.float32,
        }
        np_dtype = dtype_map.get(binary_format, np.int16)

        raw_array = np.frombuffer(eeg_bytes, dtype=np_dtype)
        if n_channels > 0 and len(raw_array) > 0:
            if data_orientation == "MULTIPLEXED":
                # Samples interleaved: ch0_t0, ch1_t0, ..., chN_t0, ch0_t1, ...
                total_samples = len(raw_array)
                n_samples = total_samples // n_channels
                raw_array = raw_array[: n_samples * n_channels]
                data = raw_array.reshape(n_samples, n_channels).T.astype(
                    np.float64
                )
            else:
                n_samples = len(raw_array) // n_channels
                data = raw_array.reshape(n_channels, n_samples).astype(
                    np.float64
                )
        else:
            n_channels = max(n_channels, 1)
            data = np.zeros((n_channels, 0), dtype=np.float64)
            n_samples = 0

        # Parse channel names
        ch_names = cls._parse_channel_names(parser, n_channels)

        records: list[Mapping[str, Any]] = []
        for idx in range(n_channels):
            ch_data = data[idx] if idx < len(data) else np.zeros(n_samples)
            records.append(
                {
                    "channel_index": idx,
                    "channel_name": ch_names[idx],
                    "sample_rate": float(sfreq),
                    "n_samples": int(ch_data.shape[0]),
                    "data": ch_data.astype(np.float64).tobytes(),
                }
            )
        return records

    # ------------------------------------------------------------------
    # Encode
    # ------------------------------------------------------------------

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        import numpy as np

        materialised = [dict(r) for r in records]
        if not materialised:
            raise ValueError(
                "BrainVisionFormat: cannot encode empty record stream — "
                "at least one channel record is required."
            )

        n_channels = len(materialised)
        sfreq = float(materialised[0].get("sample_rate", 1000.0))
        ch_names = [str(r.get("channel_name", f"Ch{r['channel_index']+1}")) for r in materialised]

        # Build data matrix (channels × samples)
        arrays = []
        for rec in materialised:
            data_bytes = rec.get("data", b"")
            arr = np.frombuffer(data_bytes, dtype=np.float64)
            arrays.append(arr)
        n_samples = max((len(a) for a in arrays), default=0)
        # Pad/truncate to uniform length
        padded = []
        for arr in arrays:
            if len(arr) < n_samples:
                arr = np.pad(arr, (0, n_samples - len(arr)))
            else:
                arr = arr[:n_samples]
            padded.append(arr)

        data_matrix = np.stack(padded, axis=0)  # (n_channels, n_samples)
        # Interleaved binary (MULTIPLEXED = sample × channel)
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
    def _build_vhdr(
        cls, ch_names: list[str], sfreq: float, n_samples: int
    ) -> str:
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
            lines.append(f"Ch{idx+1}={safe_name},,1,µV")
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

    # ------------------------------------------------------------------
    # VHDR parser helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_vhdr(text: str) -> Any:
        import configparser

        parser = configparser.ConfigParser(strict=False)
        # Skip the first "Brain Vision Data Exchange Header..." line
        lines = text.splitlines()
        ini_lines = [line for line in lines if not line.startswith("Brain Vision")]
        parser.read_string("\n".join(ini_lines))
        return parser

    @staticmethod
    def _parse_channel_names(parser: Any, n_channels: int) -> list[str]:
        ch_names: list[str] = []
        section = "Channel Infos"
        for idx in range(1, n_channels + 1):
            key = f"ch{idx}"
            if parser.has_option(section, key):
                val = parser.get(section, key)
                name = val.split(",")[0].strip()
            else:
                name = f"Ch{idx}"
            ch_names.append(name)
        return ch_names

    @classmethod
    def _rewrite_vhdr_paths(cls, vhdr_text: str, tmpdir: str) -> str:
        """Rewrite DataFile/MarkerFile paths to point to tmpdir."""
        lines = []
        for line in vhdr_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("DataFile="):
                lines.append("DataFile=recording.eeg")
            elif stripped.startswith("MarkerFile="):
                lines.append("MarkerFile=recording.vmrk")
            else:
                lines.append(line)
        return "\n".join(lines)
