"""Compression codec implementations used by ``CompressedFileFormat``.

One class per file. Each codec implements
:class:`pirn.connectors.file_formats.codec.Codec`. Optional SDK
dependencies are imported only when a codec compresses or decompresses,
so they are not pulled in unless the user opts into the relevant extra
(``pirn-core[zstd]``, ``pirn-core[snappy]``, ``pirn-core[lz4]``).
"""
