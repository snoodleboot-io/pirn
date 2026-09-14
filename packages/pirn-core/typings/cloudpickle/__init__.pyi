# Local type stub for ``cloudpickle`` (ships no py.typed). Declares the subset
# pirn-core uses. ``loads`` is ``pickle.loads``: the object it rebuilds is
# whatever was pickled, so its result is ``Any`` exactly as typeshed types pickle.
from collections.abc import Callable
from pickle import PickleBuffer
from typing import Any

DEFAULT_PROTOCOL: int


def dumps(
    obj: object,
    protocol: int | None = None,
    buffer_callback: Callable[[PickleBuffer], object] | None = None,
) -> bytes: ...


def loads(
    data: bytes | bytearray | memoryview,
    /,
    *,
    fix_imports: bool = True,
    encoding: str = "ASCII",
    errors: str = "strict",
) -> Any: ...
