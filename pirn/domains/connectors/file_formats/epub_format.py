"""``EpubFormat`` — EPUB e-book encoder/decoder backed by ``ebooklib``.

EPUB is a zipped bundle of HTML chapters with a manifest. Reads use
``ebooklib.epub.read_epub``, walking each chapter (item type
``ITEM_DOCUMENT``) and extracting plain text. Writes assemble a fresh
EPUB with one chapter per record.

Records have shape ``{"chapter_id": str, "title": str, "text": str}``.

Round-trip is text-only — HTML markup, embedded media, and CSS are not
preserved.

Install: ``pip install pirn[epub]``.
"""

from __future__ import annotations

import io
import os
import tempfile
from html.parser import HTMLParser
from typing import Any, Iterable, Mapping

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class _HtmlStripper(HTMLParser):
    """Tiny HTML-to-text fallback for EPUB chapter bodies."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag in {"p", "br", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self._parts.append("\n")

    def text(self) -> str:
        joined = "".join(self._parts)
        return "\n".join(
            line.strip() for line in joined.splitlines() if line.strip()
        )


class EpubFormat(BatchFileFormat):
    """Whole-file EPUB encoder/decoder."""

    def __init__(
        self,
        title: str = "pirn",
        language: str = "en",
        identifier: str = "pirn-epub",
    ) -> None:
        if not isinstance(title, str) or not title:
            raise ValueError(
                "EpubFormat: title must be a non-empty string"
            )
        if not isinstance(language, str) or not language:
            raise ValueError(
                "EpubFormat: language must be a non-empty string"
            )
        if not isinstance(identifier, str) or not identifier:
            raise ValueError(
                "EpubFormat: identifier must be a non-empty string"
            )
        self._title = title
        self._language = language
        self._identifier = identifier

    @property
    def name(self) -> str:
        return "epub"

    @property
    def title(self) -> str:
        return self._title

    @property
    def language(self) -> str:
        return self._language

    @property
    def identifier(self) -> str:
        return self._identifier

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        if not payload:
            return []
        epub = self._load_epub()
        ebooklib = self._load_ebooklib()
        with tempfile.NamedTemporaryFile(
            suffix=".epub", delete=False
        ) as handle:
            handle.write(payload)
            tmp_path = handle.name
        try:
            book = epub.read_epub(tmp_path)
            records: list[Mapping[str, Any]] = []
            for item in book.get_items():
                if item.get_type() != ebooklib.ITEM_DOCUMENT:
                    continue
                body = item.get_content()
                if isinstance(body, bytes):
                    body_text = body.decode("utf-8", errors="replace")
                else:
                    body_text = str(body)
                stripper = _HtmlStripper()
                stripper.feed(body_text)
                stripper.close()
                text = stripper.text()
                title = self._chapter_title(item) or item.get_name()
                records.append(
                    {
                        "chapter_id": item.get_id(),
                        "title": title,
                        "text": text,
                    }
                )
            return records
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        epub = self._load_epub()
        materialised = list(records)
        book = epub.EpubBook()
        book.set_identifier(self._identifier)
        book.set_title(self._title)
        book.set_language(self._language)
        chapters: list[Any] = []
        for index, record in enumerate(materialised):
            chapter_id = self._extract_str(
                record, "chapter_id", default=f"chap_{index + 1}"
            )
            title = self._extract_str(
                record, "title", default=f"Chapter {index + 1}"
            )
            text = self._extract_str(record, "text", default="")
            file_name = f"{chapter_id}.xhtml"
            chapter = epub.EpubHtml(
                title=title,
                file_name=file_name,
                lang=self._language,
                uid=chapter_id,
            )
            chapter.content = self._wrap_html(title, text)
            book.add_item(chapter)
            chapters.append(chapter)
        book.toc = tuple(chapters)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ["nav", *chapters]
        with tempfile.NamedTemporaryFile(
            suffix=".epub", delete=False
        ) as handle:
            tmp_path = handle.name
        try:
            epub.write_epub(tmp_path, book)
            with open(tmp_path, "rb") as fh:
                return fh.read()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    @staticmethod
    def _wrap_html(title: str, text: str) -> str:
        body_paragraphs = "".join(
            f"<p>{paragraph}</p>"
            for paragraph in text.split("\n\n")
            if paragraph.strip()
        )
        if not body_paragraphs:
            body_paragraphs = "<p>&nbsp;</p>"
        return (
            "<html xmlns=\"http://www.w3.org/1999/xhtml\">"
            f"<head><title>{title}</title></head>"
            f"<body><h1>{title}</h1>{body_paragraphs}</body>"
            "</html>"
        )

    @staticmethod
    def _chapter_title(item: Any) -> str | None:
        # ebooklib does not expose a stable per-item title; pull from
        # the HTML <title> tag when present.
        body = item.get_content()
        if isinstance(body, bytes):
            try:
                body_text = body.decode("utf-8", errors="replace")
            except UnicodeDecodeError:
                return None
        else:
            body_text = str(body)
        lower = body_text.lower()
        start = lower.find("<title>")
        end = lower.find("</title>")
        if start == -1 or end == -1 or end < start:
            return None
        return body_text[start + len("<title>") : end].strip() or None

    @staticmethod
    def _extract_str(
        record: Mapping[str, Any], key: str, default: str
    ) -> str:
        value = record.get(key, default)
        if value is None:
            return default
        if not isinstance(value, str):
            raise TypeError(
                f"EpubFormat: record {key!r} must be str, got "
                f"{type(value).__name__}"
            )
        return value

    @staticmethod
    def _load_epub() -> Any:
        try:
            from ebooklib import epub
        except ImportError as exc:
            raise ImportError(
                "EpubFormat requires ebooklib. Install with "
                "`pip install pirn[epub]`."
            ) from exc
        return epub

    @staticmethod
    def _load_ebooklib() -> Any:
        try:
            import ebooklib
        except ImportError as exc:
            raise ImportError(
                "EpubFormat requires ebooklib. Install with "
                "`pip install pirn[epub]`."
            ) from exc
        return ebooklib
