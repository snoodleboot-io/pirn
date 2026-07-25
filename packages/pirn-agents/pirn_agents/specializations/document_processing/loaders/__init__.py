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
