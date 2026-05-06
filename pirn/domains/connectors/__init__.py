"""Cross-cutting Source/Sink connector knots.

Connectors are organised by category and ship behind per-backend optional
extras so users only install the dependencies they need::

    pip install 'pirn[postgres]'
    pip install 'pirn[snowflake,kafka,s3]'
    pip install 'pirn[all-db,all-storage,all-stream]'

Each connector backend lives in its own module and is paired with a
configuration dataclass in a sibling module (one class per file). The
package exposes interfaces (:mod:`database_connection_pool`,
:mod:`object_store`, :mod:`message_broker`, :mod:`file_format`) that
backend implementations inherit from.
"""

__all__: list[str] = []
