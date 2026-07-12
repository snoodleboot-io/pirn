"""Document loaders (F25-S1 / PIR-571).

A provider-neutral loader set: each concrete loader turns the raw bytes of one
source object into a normalized
:class:`~pirn_agents.specializations.document_processing.loaders.loaded_document.LoadedDocument`
behind the shared
:class:`~pirn_agents.specializations.document_processing.loaders.loader.Loader`
interface. Backend-backed loaders (PDF, HTML, docx) lazily import their parser
through the ``pdf`` / ``html`` / ``docx`` extras, so importing this package pulls
no backend. Markdown, code, CSV, and JSON loaders use only the stdlib.

Multimodal loaders (image/audio) are deferred to F15 (Phase 5, not merged); the
``Loader`` interface is the seam they will implement.
"""

from __future__ import annotations

from pirn_agents.specializations.document_processing.loaders.code_loader import CodeLoader
from pirn_agents.specializations.document_processing.loaders.csv_loader import CsvLoader
from pirn_agents.specializations.document_processing.loaders.docx_loader import DocxLoader
from pirn_agents.specializations.document_processing.loaders.html_loader import HtmlLoader
from pirn_agents.specializations.document_processing.loaders.json_loader import JsonLoader
from pirn_agents.specializations.document_processing.loaders.loaded_document import (
    LoadedDocument,
)
from pirn_agents.specializations.document_processing.loaders.loader import Loader
from pirn_agents.specializations.document_processing.loaders.markdown_loader import (
    MarkdownLoader,
)
from pirn_agents.specializations.document_processing.loaders.pdf_loader import PdfLoader

__all__: list[str] = [
    "CodeLoader",
    "CsvLoader",
    "DocxLoader",
    "HtmlLoader",
    "JsonLoader",
    "LoadedDocument",
    "Loader",
    "MarkdownLoader",
    "PdfLoader",
]
