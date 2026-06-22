"""``PdfFormat`` — Portable Document Format (PDF) encoder/decoder.

Reads use ``pypdf`` to extract per-page text; writes use ``reportlab`` to
emit a basic text-only document (one page per record). PDFs cannot be
decoded incrementally without page-index parsing, so this is a
:class:`BatchFileFormat`.

Round-trip is intrinsically lossy: rendering a record's text via
``reportlab`` produces a fresh PDF that ``pypdf`` then re-extracts. Byte
equality is never preserved; tests should assert text-content survival
with whitespace normalisation.

Security: pirn does not sandbox ``pypdf``. Malformed PDFs may trigger
upstream library bugs. Treat untrusted payloads accordingly.

Install: ``pip install pirn[pdf]``.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class PdfFormat(BatchFileFormat):
    """Whole-file PDF encoder/decoder."""

    def __init__(self, extract_layout: bool = False) -> None:
        if not isinstance(extract_layout, bool):
            raise TypeError(
                f"PdfFormat: extract_layout must be a bool, got {type(extract_layout).__name__}"
            )
        self._extract_layout = extract_layout

    @property
    def name(self) -> str:
        return "pdf"

    @property
    def extract_layout(self) -> bool:
        return self._extract_layout

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        pypdf = self._load_pypdf()
        reader = pypdf.PdfReader(io.BytesIO(payload))
        records: list[Mapping[str, Any]] = []
        for index, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            record: dict[str, Any] = {
                "page_number": index + 1,
                "text": text,
            }
            if self._extract_layout:
                record["bbox"] = self._page_bbox(page)
            records.append(record)
        return records

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        reportlab_canvas = self._load_reportlab_canvas()
        reportlab_pagesizes = self._load_reportlab_pagesizes()
        materialised: list[Mapping[str, Any]] = list(records)
        buf = io.BytesIO()
        page_size = reportlab_pagesizes.LETTER
        canvas = reportlab_canvas.Canvas(buf, pagesize=page_size)
        if not materialised:
            # reportlab refuses to save without a page; emit a single
            # blank page so the resulting payload is still a valid PDF.
            canvas.showPage()
        else:
            for record in materialised:
                if "text" not in record:
                    raise ValueError(
                        "PdfFormat: record missing required 'text' "
                        f"field — got keys {list(record.keys())}"
                    )
                text = record["text"]
                if not isinstance(text, str):
                    raise TypeError(
                        f"PdfFormat: 'text' must be a string, got {type(text).__name__}"
                    )
                self._draw_text(canvas, text, page_size)
                canvas.showPage()
        canvas.save()
        return buf.getvalue()

    @staticmethod
    def _draw_text(canvas: Any, text: str, page_size: tuple[float, float]) -> None:
        margin = 72.0  # one inch
        _, height = page_size
        text_object = canvas.beginText(margin, height - margin)
        text_object.setFont("Helvetica", 12)
        for line in text.splitlines() or [""]:
            text_object.textLine(line)
        canvas.drawText(text_object)

    @staticmethod
    def _page_bbox(page: Any) -> Mapping[str, float]:
        mediabox = page.mediabox
        return {
            "x0": float(mediabox.left),
            "y0": float(mediabox.bottom),
            "x1": float(mediabox.right),
            "y1": float(mediabox.top),
        }

    @staticmethod
    def _load_pypdf() -> Any:
        try:
            import pypdf
        except ImportError as exc:
            raise ImportError(
                "PdfFormat requires pypdf. Install with `pip install pirn[pdf]`."
            ) from exc
        return pypdf

    @staticmethod
    def _load_reportlab_canvas() -> Any:
        try:
            from reportlab.pdfgen import canvas
        except ImportError as exc:
            raise ImportError(
                "PdfFormat requires reportlab. Install with `pip install pirn[pdf]`."
            ) from exc
        return canvas

    @staticmethod
    def _load_reportlab_pagesizes() -> Any:
        try:
            from reportlab.lib import pagesizes
        except ImportError as exc:
            raise ImportError(
                "PdfFormat requires reportlab. Install with `pip install pirn[pdf]`."
            ) from exc
        return pagesizes
