"""``TfSavedModelFormat`` — TensorFlow SavedModel directory bundle.

TensorFlow's SavedModel is a directory layout (``saved_model.pb`` plus a
``variables/`` subdirectory and optional ``assets/``). Connectors deal in
byte payloads, so this format wraps the directory in a ZIP archive on
encode and extracts it back to a temporary directory on decode.

ML artefacts do not fit the row-of-data model — each artefact is one
"row". :meth:`_decode_full` yields a single record exposing the
extracted directory path; callers (typically tests or downstream
loaders) are responsible for keeping the path alive while they read it.
A :class:`tempfile.TemporaryDirectory` reference is attached to the
record under ``_tmpdir`` so garbage collection does not prematurely
unlink the bytes — drop the reference once consumed.

:meth:`_encode_full` accepts ``saved_model_path`` pointing at an
existing SavedModel directory and zips its contents.

Security: pirn does not sandbox ``tensorflow``. Malicious SavedModels
may contain arbitrary ops; treat untrusted payloads accordingly. ZIP
extraction guards against absolute / parent-directory member paths.

Install: ``pip install pirn[tensorflow]``.
"""

from __future__ import annotations

import io
import os
import tempfile
import zipfile
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class TfSavedModelFormat(BatchFileFormat):
    """Whole-file TensorFlow SavedModel encoder/decoder (zip-bundled)."""

    def __init__(self) -> None:
        # No configuration: the zip-bundle convention is fixed.
        return

    @property
    def name(self) -> str:
        return "tf_saved_model"

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError(
                "TfSavedModelFormat: payload must be bytes, "
                f"got {type(payload).__name__}"
            )
        tf = self._load_tensorflow()
        tmpdir = tempfile.TemporaryDirectory(prefix="pirn-tf-savedmodel-")
        try:
            with zipfile.ZipFile(io.BytesIO(bytes(payload))) as archive:
                self._safe_extract(archive, tmpdir.name)
            try:
                model = tf.saved_model.load(tmpdir.name)
            except Exception as exc:
                raise ValueError(
                    "TfSavedModelFormat: tf.saved_model.load failed "
                    f"— {exc}"
                ) from exc
        except Exception:
            tmpdir.cleanup()
            raise
        signature_keys: list[str] = []
        signatures = getattr(model, "signatures", None)
        if signatures is not None:
            try:
                signature_keys = [str(key) for key in signatures]
            except (AttributeError, TypeError):
                signature_keys = []
        record: dict[str, Any] = {
            "saved_model_path": tmpdir.name,
            "signatures": signature_keys,
            "metadata": {
                "format": "tf_saved_model",
            },
            "_tmpdir": tmpdir,
        }
        return [record]

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        materialised: list[Mapping[str, Any]] = list(records)
        if len(materialised) != 1:
            raise ValueError(
                "TfSavedModelFormat: expected exactly one record "
                "containing 'saved_model_path', got "
                f"{len(materialised)}"
            )
        record = materialised[0]
        if "saved_model_path" not in record:
            raise ValueError(
                "TfSavedModelFormat: record missing required "
                "'saved_model_path' key"
            )
        path = record["saved_model_path"]
        if not isinstance(path, str) or not path:
            raise ValueError(
                "TfSavedModelFormat: 'saved_model_path' must be a "
                f"non-empty string, got {path!r}"
            )
        if not os.path.isdir(path):
            raise ValueError(
                "TfSavedModelFormat: 'saved_model_path' is not a "
                f"directory: {path}"
            )
        return self._zip_directory(path)

    @staticmethod
    def _zip_directory(directory: str) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(
            buffer, "w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for dirpath, _dirnames, filenames in os.walk(directory):
                for filename in filenames:
                    full = os.path.join(dirpath, filename)
                    arcname = os.path.relpath(full, directory)
                    archive.write(full, arcname=arcname)
        return buffer.getvalue()

    @staticmethod
    def _safe_extract(archive: zipfile.ZipFile, target: str) -> None:
        target_root = os.path.realpath(target)
        for member in archive.infolist():
            member_path = os.path.realpath(
                os.path.join(target, member.filename)
            )
            if not (
                member_path == target_root
                or member_path.startswith(target_root + os.sep)
            ):
                raise ValueError(
                    "TfSavedModelFormat: zip member escapes target "
                    f"directory — {member.filename!r}"
                )
        archive.extractall(target)

    @staticmethod
    def _load_tensorflow() -> Any:
        try:
            import tensorflow as tf
        except ImportError as exc:
            raise ImportError(
                "TfSavedModelFormat requires tensorflow. Install with "
                "`pip install pirn[tensorflow]`."
            ) from exc
        return tf
