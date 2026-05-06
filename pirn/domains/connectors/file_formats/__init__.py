"""Concrete :class:`FileFormat` implementations.

Each format module declares one class implementing
:class:`pirn.domains.connectors.file_format.FileFormat`. Streaming
formats inherit from :class:`StreamingFileFormat`; batch-only formats
inherit from :class:`BatchFileFormat`.

Compression is layered via :class:`CompressedFileFormat`. Multi-file
archives get :class:`ArchiveFileFormat`.
"""
