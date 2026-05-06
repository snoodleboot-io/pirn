"""Configuration dataclass for :class:`HDFSStore`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class HDFSConfig(ConnectionConfig):
    """Configuration for an HDFS object store via WebHDFS or PyArrow HDFS.

    Attributes
    ----------
    namenode_host:
        Hostname or IP of the HDFS NameNode.
    namenode_port:
        WebHDFS REST port (default 50070) or native HDFS port (default 8020).
    user:
        Hadoop user name for authentication.
    base_path:
        Root path prefix for all key operations (e.g. ``/data``).
    use_webhdfs:
        When True (default) uses the WebHDFS REST API via ``requests``.
        When False uses PyArrow HDFS bindings (native protocol).
    chunk_size:
        Streaming read chunk size in bytes.
    """

    namenode_host: str = "localhost"
    namenode_port: int = 50070
    user: str = ""
    base_path: str = "/"
    use_webhdfs: bool = True
    chunk_size: int = 1 << 20

    sensitive_fields: ClassVar[tuple[str, ...]] = ()
