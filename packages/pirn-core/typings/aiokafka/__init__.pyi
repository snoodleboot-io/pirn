# Local type stub for ``aiokafka`` (ships no py.typed). Declares exactly the subset
# pirn-core uses: a consumer iterated for records and a producer that sends and
# waits. Client options are forwarded verbatim to the SDK, so they are accepted
# as keyword ``object`` values. A consumer's key/value deserializers are
# configurable, so a record's key and value are whatever they produce
# (``bytes`` without one). Extend when new API is used.
from collections.abc import AsyncIterator, Sequence


class ConsumerRecord:
    topic: str
    partition: int
    offset: int
    timestamp: int
    key: object
    value: object
    headers: Sequence[tuple[str, bytes]]


class RecordMetadata:
    topic: str
    partition: int
    offset: int


class AIOKafkaConsumer:
    def __init__(self, *topics: str, **config: object) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def commit(self) -> None: ...
    def __aiter__(self) -> AsyncIterator[ConsumerRecord]: ...
    async def __anext__(self) -> ConsumerRecord: ...


class AIOKafkaProducer:
    def __init__(self, **config: object) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def flush(self) -> None: ...
    async def send_and_wait(
        self,
        topic: str,
        value: bytes | None = None,
        key: bytes | None = None,
        partition: int | None = None,
        timestamp_ms: int | None = None,
        headers: Sequence[tuple[str, bytes]] | None = None,
    ) -> RecordMetadata: ...
