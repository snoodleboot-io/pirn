"""``MarkdownFormat`` — CommonMark Markdown encoder/decoder.

Reads parse the document with ``markdown-it-py`` and walk the token
stream; writes emit a minimal Markdown skeleton from records. Three
split modes:

* ``"heading"`` — each top-level (``#``) heading and the prose under
  it become a record. Record shape:
  ``{"text": str, "level": int, "title": str | None}``.
* ``"paragraph"`` — each paragraph token becomes a record. Record
  shape: ``{"text": str, "level": 0, "title": None}``.
* ``"file"`` — the whole file is a single record with the rendered
  HTML as ``"text"``. Record shape:
  ``{"text": str, "level": 0, "title": None}``.

Markdown is a textual format with no random access — implemented as a
:class:`BatchFileFormat`.

Install: ``pip install pirn[markdown]``.
"""

from __future__ import annotations

from typing import Any, ClassVar, Iterable, Mapping

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class MarkdownFormat(BatchFileFormat):
    """Whole-file Markdown encoder/decoder."""

    _supported_split_modes: ClassVar[frozenset[str]] = frozenset(
        {"heading", "paragraph", "file"}
    )

    def __init__(
        self,
        split_on: str = "heading",
        encoding: str = "utf-8",
    ) -> None:
        if not isinstance(split_on, str):
            raise TypeError(
                "MarkdownFormat: split_on must be str"
            )
        if split_on not in self._supported_split_modes:
            raise ValueError(
                "MarkdownFormat: split_on must be one of "
                f"{sorted(self._supported_split_modes)}, got "
                f"{split_on!r}"
            )
        if not isinstance(encoding, str):
            raise TypeError(
                "MarkdownFormat: encoding must be str"
            )
        if not encoding:
            raise ValueError(
                "MarkdownFormat: encoding must be non-empty"
            )
        self._split_on = split_on
        self._encoding = encoding

    @property
    def name(self) -> str:
        return "markdown"

    @property
    def split_on(self) -> str:
        return self._split_on

    @property
    def encoding(self) -> str:
        return self._encoding

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        if not payload:
            return []
        text = payload.decode(self._encoding)
        if self._split_on == "file":
            renderer = self._load_markdown()
            html = renderer.markdown(text)
            return [{"text": html, "level": 0, "title": None}]

        markdown_it = self._load_markdown_it()
        parser = markdown_it.MarkdownIt()
        tokens = parser.parse(text)
        if self._split_on == "heading":
            return self._records_by_heading(tokens)
        return self._records_by_paragraph(tokens)

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        materialised = list(records)
        if self._split_on == "heading":
            return self._encode_heading(materialised).encode(
                self._encoding
            )
        if self._split_on == "paragraph":
            return self._encode_paragraph(materialised).encode(
                self._encoding
            )
        return self._encode_file(materialised).encode(self._encoding)

    @staticmethod
    def _records_by_heading(
        tokens: list[Any],
    ) -> list[Mapping[str, Any]]:
        records: list[Mapping[str, Any]] = []
        current_title: str | None = None
        current_level: int = 0
        body_lines: list[str] = []
        in_heading = False
        in_heading_level = 0

        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token.type == "heading_open":
                # Close previous section before starting a new one.
                MarkdownFormat._flush_section(records, current_title, current_level, body_lines)
                body_lines = []
                in_heading = True
                in_heading_level = int(token.tag[1:])
                current_title = ""
                current_level = in_heading_level
                index += 1
                continue
            if token.type == "heading_close":
                in_heading = False
                index += 1
                continue
            if in_heading and token.type == "inline":
                current_title = token.content
                index += 1
                continue
            if token.type == "inline":
                body_lines.append(token.content)
                index += 1
                continue
            index += 1
        MarkdownFormat._flush_section(records, current_title, current_level, body_lines)
        return records

    @staticmethod
    def _flush_section(
        records: list[Mapping[str, Any]],
        current_title: str | None,
        current_level: int,
        body_lines: list[str],
    ) -> None:
        if current_title is None and not body_lines:
            return
        records.append(
            {
                "text": "\n".join(body_lines).strip(),
                "level": current_level,
                "title": current_title,
            }
        )

    @staticmethod
    def _records_by_paragraph(
        tokens: list[Any],
    ) -> list[Mapping[str, Any]]:
        records: list[Mapping[str, Any]] = []
        in_paragraph = False
        for token in tokens:
            if token.type == "paragraph_open":
                in_paragraph = True
                continue
            if token.type == "paragraph_close":
                in_paragraph = False
                continue
            if in_paragraph and token.type == "inline":
                records.append(
                    {
                        "text": token.content,
                        "level": 0,
                        "title": None,
                    }
                )
        return records

    @classmethod
    def _encode_heading(
        cls, records: list[Mapping[str, Any]]
    ) -> str:
        parts: list[str] = []
        for record in records:
            text = cls._extract_text(record)
            title = record.get("title")
            level_value = record.get("level", 1)
            try:
                level = int(level_value) if level_value else 1
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "MarkdownFormat: record 'level' must be an "
                    f"integer, got {level_value!r}"
                ) from exc
            if level < 1:
                level = 1
            if level > 6:
                level = 6
            heading_marker = "#" * level
            if title is not None:
                if not isinstance(title, str):
                    raise TypeError(
                        "MarkdownFormat: record 'title' must be str "
                        "or None"
                    )
                parts.append(f"{heading_marker} {title}\n\n")
            if text:
                parts.append(f"{text}\n\n")
        return "".join(parts)

    @classmethod
    def _encode_paragraph(
        cls, records: list[Mapping[str, Any]]
    ) -> str:
        parts: list[str] = []
        for record in records:
            text = cls._extract_text(record)
            parts.append(f"{text}\n\n")
        return "".join(parts)

    @classmethod
    def _encode_file(
        cls, records: list[Mapping[str, Any]]
    ) -> str:
        return "".join(cls._extract_text(record) for record in records)

    @staticmethod
    def _extract_text(record: Mapping[str, Any]) -> str:
        if "text" not in record:
            raise ValueError(
                "MarkdownFormat: record missing required 'text' key"
            )
        text = record["text"]
        if not isinstance(text, str):
            raise TypeError(
                "MarkdownFormat: record 'text' value must be str, "
                f"got {type(text).__name__}"
            )
        return text

    @staticmethod
    def _load_markdown_it() -> Any:
        try:
            import markdown_it
        except ImportError as exc:
            raise ImportError(
                "MarkdownFormat requires markdown-it-py. Install with "
                "`pip install pirn[markdown]`."
            ) from exc
        return markdown_it

    @staticmethod
    def _load_markdown() -> Any:
        try:
            import markdown
        except ImportError as exc:
            raise ImportError(
                "MarkdownFormat requires markdown. Install with "
                "`pip install pirn[markdown]`."
            ) from exc
        return markdown
