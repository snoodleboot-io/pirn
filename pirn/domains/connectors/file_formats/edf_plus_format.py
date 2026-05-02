"""``EdfPlusFormat`` — EDF+ batch encoder/decoder (extends EdfFormat).

EDF+ extends the European Data Format with Time-stamped Annotation
Lists (TAL). Annotations are emitted as an extra record alongside the
signal-channel records::

    {
        "_edfplus_annotations": [
            {"onset": float, "duration": float, "text": str},
            ...
        ]
    }

On encode, if that record is present in the input stream, the
annotations are written back into the EDF+ file.

Install: ``pip install pirn[health]``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pirn.domains.connectors.file_formats.edf_format import EdfFormat


class EdfPlusFormat(EdfFormat):
    """EDF+ encoder/decoder — adds TAL annotation handling to EdfFormat."""

    # EDF+ files use the same .edf extension; the "+" is declared in
    # the header, not the filename.
    _file_suffix = ".edf"

    @property
    def name(self) -> str:
        return "edf+"

    @classmethod
    def _read_signals(
        cls, pyedflib: Any, path: str
    ) -> list[Mapping[str, Any]]:
        records = super()._read_signals(pyedflib, path)
        annotations = cls._read_annotations(pyedflib, path)
        if annotations is not None:
            records = list(records) + [{"_edfplus_annotations": annotations}]
        return records

    @staticmethod
    def _read_annotations(
        pyedflib: Any, path: str
    ) -> list[dict[str, Any]] | None:
        annotations: list[dict[str, Any]] = []
        try:
            with pyedflib.EdfReader(path) as reader:
                raw = reader.readAnnotations()
                # readAnnotations() returns (onsets, durations, descriptions)
                if raw is None or len(raw) == 0:
                    return annotations
                onsets, durations, descriptions = raw
                for onset, duration, text in zip(onsets, durations, descriptions):
                    annotations.append(
                        {
                            "onset": float(onset),
                            "duration": float(duration),
                            "text": str(text),
                        }
                    )
        except Exception:
            return annotations
        return annotations

    @staticmethod
    def _write_annotations(
        writer: Any, annotation_record: dict[str, Any] | None
    ) -> None:
        if annotation_record is None:
            return
        annotations = annotation_record.get("_edfplus_annotations", [])
        for ann in annotations:
            try:
                writer.writeAnnotation(
                    float(ann.get("onset", 0.0)),
                    float(ann.get("duration", -1.0)),
                    str(ann.get("text", "")),
                )
            except Exception:
                pass
