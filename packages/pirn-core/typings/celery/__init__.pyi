# Local type stub for ``celery`` (ships no py.typed). Declares exactly the subset
# pirn-core uses: building an app, updating its config, sending a task by name and
# registering a worker task. Task arguments and results cross a pickle boundary,
# so a result's ``get`` returns whatever the worker returned. Extend when new API
# is used.
from collections.abc import Callable, Mapping, Sequence
from typing import Any, TypeVar

_F = TypeVar("_F", bound=Callable[..., object])


class AsyncResult:
    id: str
    def get(self, timeout: float | None = None, propagate: bool = True) -> Any: ...
    def ready(self) -> bool: ...


class Settings:
    def update(self, **options: object) -> None: ...


class Celery:
    conf: Settings
    def __init__(
        self,
        main: str | None = None,
        *,
        broker: str | None = None,
        backend: str | None = None,
        **options: object,
    ) -> None: ...
    def send_task(
        self,
        name: str,
        args: Sequence[object] | None = None,
        kwargs: Mapping[str, object] | None = None,
        **options: object,
    ) -> AsyncResult: ...
    def task(self, *, name: str | None = None, **options: object) -> Callable[[_F], _F]: ...
