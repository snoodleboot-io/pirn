"""``HtmlFormat`` — HTML encoder/decoder.

Reads use ``beautifulsoup4`` with the ``lxml`` parser; writes emit a
minimal hand-rolled HTML document. HTML decoding requires the entire
payload to build the parse tree, so this is a :class:`BatchFileFormat`.

Two decode modes:

* default: yield one record per document with ``title``, cleaned
  ``text`` (stripped of script/style noise) and a list of ``links``;
* ``extract_tables=True``: yield one record per ``<tr>`` row, where
  every cell becomes a string-keyed entry (``"col_0"``, ``"col_1"``, …
  unless a header row is present).

Encoding is symmetrical only for the default mode: each record's
``title`` and ``text`` go into a minimal ``<html>`` skeleton.

Security: pirn does not sandbox the parsers. The ``lxml`` parser is run
without external entity resolution by default, but callers should still
treat untrusted HTML as adversarial and avoid evaluating any embedded
scripts.

Install: ``pip install pirn[html]``.
"""

from __future__ import annotations

import html
import io
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class HtmlFormat(BatchFileFormat):
    """Whole-file HTML encoder/decoder."""

    def __init__(self, extract_tables: bool = False) -> None:
        if not isinstance(extract_tables, bool):
            raise TypeError(
                f"HtmlFormat: extract_tables must be a bool, got {type(extract_tables).__name__}"
            )
        self._extract_tables = extract_tables

    @property
    def name(self) -> str:
        return "html"

    @property
    def extract_tables(self) -> bool:
        return self._extract_tables

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        bs4 = self._load_bs4()
        # Verify lxml is importable so the parser argument below works.
        self._load_lxml()
        soup = bs4.BeautifulSoup(io.BytesIO(payload), features="lxml")
        if self._extract_tables:
            return self._decode_tables(soup)
        return [self._decode_document(soup)]

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        materialised = list(records)
        body_chunks: list[str] = []
        title = ""
        for record in materialised:
            record_title = record.get("title")
            if record_title is not None and not isinstance(record_title, str):
                raise TypeError(
                    "HtmlFormat: 'title' must be a string when "
                    f"provided, got {type(record_title).__name__}"
                )
            text = record.get("text")
            if text is not None and not isinstance(text, str):
                raise TypeError(
                    f"HtmlFormat: 'text' must be a string when provided, got {type(text).__name__}"
                )
            if record_title and not title:
                title = record_title
            if text:
                body_chunks.append(f"<p>{html.escape(text)}</p>")
        document = (
            "<!DOCTYPE html><html><head>"
            f"<title>{html.escape(title)}</title>"
            "</head><body>"
            f"{''.join(body_chunks)}"
            "</body></html>"
        )
        return document.encode("utf-8")

    def _decode_document(self, soup: Any) -> Mapping[str, Any]:
        for tag_name in ("script", "style"):
            for element in soup.find_all(tag_name):
                element.decompose()
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""
        body = soup.body if soup.body else soup
        text = " ".join(body.get_text(separator=" ").split())
        links: list[str] = []
        for anchor in soup.find_all("a"):
            href = anchor.get("href")
            if isinstance(href, str) and href:
                links.append(href)
        return {"title": title, "text": text, "links": links}

    @staticmethod
    def _decode_tables(soup: Any) -> list[Mapping[str, Any]]:
        records: list[Mapping[str, Any]] = []
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if not rows:
                continue
            header_cells = rows[0].find_all("th")
            headers: list[str] = []
            data_rows = rows
            if header_cells:
                headers = [cell.get_text(strip=True) for cell in header_cells]
                data_rows = rows[1:]
            for row in data_rows:
                cells = row.find_all(["td", "th"])
                if not cells:
                    continue
                record: dict[str, Any] = {}
                for index, cell in enumerate(cells):
                    if index < len(headers) and headers[index]:
                        key = headers[index]
                    else:
                        key = f"col_{index}"
                    record[key] = cell.get_text(strip=True)
                records.append(record)
        return records

    @staticmethod
    def _load_bs4() -> Any:
        try:
            import bs4
        except ImportError as exc:
            raise ImportError(
                "HtmlFormat requires beautifulsoup4. Install with `pip install pirn[html]`."
            ) from exc
        return bs4

    @staticmethod
    def _load_lxml() -> Any:
        try:
            import lxml
        except ImportError as exc:
            raise ImportError(
                "HtmlFormat requires lxml. Install with `pip install pirn[html]`."
            ) from exc
        return lxml
