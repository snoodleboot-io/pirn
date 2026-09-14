<!-- path: prompticorn/prompts/agents/core/core-conventions-python.md -->
# Core Conventions Python

Language:             Python 3.11+ (CI matrix runs 3.11-3.14 per package; see .github/workflows/workspace.yml)
Runtime:              CPython (no PyPy in the test matrix)
Package Manager:      uv (per-package pyproject.toml; no shared workspace lockfile — see docs/architecture/ci-pipelines.md)
Linter:               Ruff 0.15.22 (pinned in .pre-commit-config.yaml and workspace.yml; do not bump without updating both)
Formatter:           Ruff 0.15.22 (ruff format; same pin as the linter)
Abstract Class Style: interface (NotImplementedError-raising base classes; no abc.ABC, no typing.Protocol for framework interfaces)

### Naming Conventions

Files:               snake_case
Variables:          snake_case
Constants:          UPPER_SNAKE (discouraged - use pydantic-settings)
Classes/Types:      PascalCase
Functions:          snake_case
Database tables:     snake_case
Environment vars:    UPPER_SNAKE_CASE always

## Python-Specific Rules

### Type Hints
- Type hints required on all public functions (use `pyright` or `mypy` to enforce)
- Use `dataclasses` or `pydantic` for data shapes, not raw dicts
- Use `T | None` instead of `typing.Optional[T]`. This is the standard for modern python
- Use `typing.TypeAlias` for complex type aliases

### Error Handling
- Use exception hierarchies — don't raise generic `Exception`. Domain exceptions extend
  `PirnError` (`pirn.exceptions.pirn_error.PirnError`), not a bare `Exception` subclass.
- Use the `Ok` / `Err` / `Skipped` result types (`pirn.core.ok`, `pirn.core.err`,
  `pirn.core.skipped`) for knot-graph execution outcomes — **not** the third-party
  `returns` library, which is not a dependency here. `Ok` wraps a successful value,
  `Err` wraps a caught exception, `Skipped` marks a knot that did not run (e.g. gate
  closure, an `Optional` knot converting a failure). This is specific to the
  engine/execution layer; ordinary function calls outside that layer just raise.
- Never swallow errors silently — always log or re-raise with context
- Use `contextlib.contextmanager` for resource management

### Async
- Use `asyncio` — no mixing sync/async without explicit bridging
- Use `asyncpg` for async database access, not synchronous drivers
- Use `httpx` for async HTTP requests

### Imports
- Use absolute imports (no relative `..` imports)
- Group imports: stdlib → third-party → local (blank lines between)
- **NEVER use import forwarding** — do not re-export imported symbols (e.g., `from module import X` then exposing `X` at package level). This is an anti-pattern and NOT allowed. Define public API explicitly.

### Code Structure & Patterns

#### Constants & Configuration (CRITICAL)
- **NO constants allowed inside or outside of classes** — never define `CONSTANT = value` at module level OR as class constants
- **For values changeable at runtime**: use a YAML configuration file
- **For fixed configuration**: use internal class variables (not constants) or `pydantic-settings` with environment variable support
- **Never have const values outside of a class** — always use a settings file (`pydantic-settings`) for configurable values
- When asked to create constants, redirect to the appropriate configuration approach

#### Dynamic Attribute Access
- **AVOID `setattr` and `getattr`** unless absolutely necessary — these bypass type checking and make code harder to reason about
- Before using: ask yourself if there's a type-safe alternative (dataclass, pydantic model, explicit properties)
- If present: ask the user if they are creating core/framework code or generally reusable code — only acceptable for core framework code that MUST handle dynamic structures

#### Module Structure
- **ALL modules MUST have `__init__.py`** — every package directory must include an `__init__.py` file
- Verify `__init__.py` exists before adding new modules
- No implicit namespace packages allowed

#### Type Casting
- **DO NOT use type casting** (`typing.cast`, `isinstance` + cast patterns) UNLESS working with data primitives like `int`, `str`, `float`, `bool`
- Primitive conversions (e.g., `int()`, `str()`, `float()`) are acceptable
- Use proper type narrowing with `isinstance` checks instead of casting for complex types
- Design APIs to return correct types rather than requiring casts

#### Type Checking Enforcement
- **ENFORCE the use of `pyright`** while coding — run continuously during development
- Treat type errors as blocking issues
- **Strict mode is adopted per top-level subpackage, ratcheted (PIR-869).** Each package's
  `[tool.pyright]` carries a `strict = [...]` list of subpackage paths (`pirn/check`,
  `pirn_agents/caching`, ... and `<pkg>/*.py` for the modules directly under the import
  root). Every listed subpackage passes strict with 0 errors; the rest run in basic mode
  until their strict count reaches 0. The rules:
  - **new subpackages start strict** — add the path to the list in the same change that
    creates the directory;
  - **a subpackage joins the strict list when its count hits 0** — never later;
  - **a listed subpackage may not regress** — CI's `lint` job runs
    `scripts/check_pyright_strict_list.py`, which measures every subpackage in strict mode
    and fails on a regression, on a 0-error subpackage missing from the list, or on a listed
    path that is not a subpackage.
  - the remaining per-subpackage counts are the burn-down table in
    `docs/architecture/ci-pipelines.md` (regenerate it with
    `python scripts/check_pyright_strict_list.py packages/<dist> --table`).
- Fixing strict errors means real annotations, not `Any`: type the third-party return you
  actually use (`dict[str, Any]` for a JSON payload, a small `TypedDict`/dataclass for a
  known shape), narrow with `isinstance` on a genuinely unknown value, and keep the
  connector pattern of a lazily imported optional SDK typed as `Any` at the import.
  `# pyright: ignore[<rule>]` only with a one-line reason on the same line.
- **`reportUnnecessaryIsInstance` is the one strict rule the house style contradicts**:
  `process()` and constructor validation is explicit — type check, then value check,
  `TypeError` before `ValueError` (`docs/contributing/domain-knots.md`) — because knot inputs
  are runtime-bound. Keep the guard. In a strict-listed subpackage suppress the rule per
  file with a two-line header above the module docstring — a config override does not
  apply inside `strict` paths, and pyright rejects trailing text on a directive line, so
  the reason goes on the next line:
  ```python
  # pyright: reportUnnecessaryIsInstance=false
  # runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
  ```
  Never satisfy the rule by deleting the check.
- **Optional extras inside a strict-listed subpackage**: CI's per-package image may not
  carry an extra (`lance` is one), and `reportMissingImports = "none"` in the package
  config does not apply inside `strict` paths. A lazily imported optional dependency
  therefore carries `# pyright: ignore[reportMissingImports]` (and
  `reportUnknownVariableType` on the names it binds) with the reason on the same line.
  Locally, where the extra is installed, the ignore is inert; strict does not enable
  `reportUnnecessaryTypeIgnoreComment`.
- No commits with type errors or `Any` types without explicit justification

### Testing

- Framework: `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"` — no `@pytest.mark.asyncio`
  needed) + `pytest-cov`. Every package's own `[tool.pytest.ini_options]` sets these; there
  is no shared root config.
- Layout: tests are **NOT co-located** with source. Each package mirrors its source tree
  under `packages/<pkg>/tests/{unit,integration,...}` — e.g.
  `packages/pirn-core/pirn/backends/azure.py` is tested by
  `packages/pirn-core/tests/unit/backends/test_azure.py`. Standard subdirectories seen
  across packages: `unit/`, `integration/`, `slow/`, `perf/`, `security/`, `smoke/`,
  `end_to_end/`, `mutation/` — not every package uses every one; add a subdirectory only
  when a test genuinely belongs to that category.
- Markers: tag anything that is not a fast, isolated unit test — `slow`, `heavy` (large ML
  deps like torch/tensorflow), `cross_domain` (needs more than one pirn package installed;
  skipped in per-package CI, run by the `unified` cross-domain suite), `mutation`, or a
  `needs_<backend>` marker (`needs_postgres`, `needs_valkey`, `needs_kafka`, `needs_s3`,
  `needs_dask`, `needs_ray`, `needs_celery`) for anything requiring a real external
  service. `--strict-markers` is on: an unregistered marker fails collection, so add new
  markers to `[tool.pytest.ini_options] markers` in that package's `pyproject.toml`.
- Coverage: `pytest --cov=<import_pkg> --cov-report=xml` per package in CI, uploaded to
  Codecov per package (not aggregated workspace-wide). No hard percentage gate is
  enforced today; write tests for every branch a change touches rather than chasing a
  number.
- Mocking: prefer a small hand-written fake over `unittest.mock` when faking one of this
  codebase's own interfaces — the NotImplementedError base-class style
  (`.claude/conventions/languages/python.md` "Abstract Classes and Interfaces" below)
  makes a minimal fake subclass cheap to write and far more readable at the call site than
  a `MagicMock` with `.return_value` chains. Reach for `unittest.mock`
  (`Mock`/`MagicMock`/`AsyncMock`, `monkeypatch`) for third-party clients and I/O boundaries
  (cloud SDKs, DB drivers, HTTP clients) where writing a fake would mean re-implementing
  someone else's API surface.

### Code Style
- Follow PEP 8 (enforced by Ruff)
- Use f-strings for string formatting
- Use `dataclasses` for simple data containers
- Use `pydantic` for complex validation
- Unless the code is a framework layer or there is a strong necessity - DO NOT use setattr or getattr.

### Python Styling and Conventions

#### Properties Over Direct Access
- **Use properties** for attribute access control - never access fields directly when get/set logic is needed
- Use `@property` decorator with getters/setters instead of `get_x()` / `set_x()` methods
- Use `@property.deleter` when cleanup logic is needed on attribute deletion
- Prevent setting when inappropriate by raising `AttributeError` or `TypeError` in setters

```python
class WidgetFormat:
    def __init__(self, schema_version: int) -> None:
        self._schema_version = schema_version

    @property
    def schema_version(self) -> int:
        """Read-only — fixed at construction, never mutated after."""
        return self._schema_version
```

Note the interaction with the Knot rules elsewhere in this repo
(`docs/contributing/knot-design-rules.md`, Rule 4): a `Knot` subclass must **not** expose
`@property` fields at all, even read-only ones — that rule is stricter than this general
Python guideline and takes precedence for anything that subclasses `Knot`. This
properties guidance applies to ordinary (non-Knot) classes such as the connector/
file-format classes above.

#### Public/Protected/Private Scoping
- Use single underscore `_` prefix for protected/internal attributes and methods
- Use double underscore `__` prefix for private attributes (name mangling when needed)
- Protected methods should not be called from outside the class hierarchy

```python
class DataProcessor:
    def __init__(self) -> None:
        self.public_field: str = "visible"
        self._internal_state: dict = {}  # Protected
        self.__private_cache: dict = {}  # Private (name mangled)

    def public_method(self) -> None:
        """Part of public API."""
        pass

    def _helper_method(self) -> None:
        """Protected - for subclass use only."""
        pass

    def __internal_cleanup(self) -> None:
        """Private - internal use only."""
        pass
```

#### Decorators and Design Patterns
- Use `@staticmethod` for functions that don't access instance state
- Use `@classmethod` for factory methods and alternate constructors
- Use `@property` for computed attributes without side effects
- Use `@functools.cached_property` for expensive computations that should be cached
- Use `@functools.wraps` when creating decorators
- Use `@contextlib.contextmanager` for creating context managers

```python
from functools import cached_property, wraps
from contextlib import contextmanager
from typing import Iterator

class ExpensiveComputation:
    @cached_property
    def heavy_result(self) -> dict:
        """Computed once and cached."""
        return self._expensive_operation()

    @staticmethod
    def utility_function(x: int) -> int:
        """Doesn't need self."""
        return x * 2

    @classmethod
    def from_config(cls, config: dict) -> "ExpensiveComputation":
        """Factory method."""
        return cls(**config)

def my_decorator(func):
    @wraps(func)  # Preserves function metadata
    def wrapper(*args, **kwargs):
        print("Before call")
        return func(*args, **kwargs)
    return wrapper
```

#### Asynchrony and Async Constructs
- Use `async`/`await` for I/O-bound operations
- Use `asyncio` for concurrency - never mix sync/async without explicit bridging
- Use `async with` for async context managers
- Use `async for` for async iterators
- Never use `time.sleep()` in async code - use `await asyncio.sleep()`

```python
class RedisTransport(DataTransport):
    """See docs/architecture/extension-points.md for the full DataTransport contract."""

    async def write(self, run_id: str, knot_id: str, value: Any) -> TransportHandle:
        # Every framework extension point method that does I/O is async, even
        # backends that are themselves synchronous under the hood — the
        # executor always awaits, so a sync-only backend still declares async
        # methods and does its blocking call inline (or via
        # asyncio.to_thread for a call that would otherwise stall the loop).
        ...

    async def read(self, handle: TransportHandle) -> Any:
        ...
```

#### Context Managers (sync and async)
- **ALWAYS use context managers** for resource management (files, connections, locks)
- Use `contextlib.contextmanager` for simple sync context managers
- Use `contextlib.asynccontextmanager` for async context managers
- Never manually manage `connect()`/`disconnect()` or `open()`/`close()` without context managers
- Use `contextlib.closing()` for objects with close() but no context manager

```python
from contextlib import contextmanager, asynccontextmanager, closing
from typing import Iterator
import sqlite3

@contextmanager
def database_connection(db_path: str) -> Iterator[sqlite3.Connection]:
    """Sync context manager for database connections."""
    conn = sqlite3.connect(db_path)
    try:
        yield conn
    finally:
        conn.close()

# Usage - always use context managers
with database_connection("app.db") as conn:
    conn.execute("SELECT * FROM users")

# For objects with close() but no context manager
from urllib.request import urlopen
with closing(urlopen("https://example.com")) as response:
    data = response.read()
```

#### No Module-Level Functions (enumerated exemption)
- **Methods belong to classes.** Module-level functions are allowed only as documented public
  entry points listed in `scripts/check_conventions.py`'s `_MODULE_LEVEL_FUNCTION_ALLOWLIST`
  (keyed `<package>:<dotted.module>:<function>`, one-line reason each — PIR-869); everything
  else is a `@staticmethod` on a class. The gate (`module_level_function`) counts every
  module-level `def` not on the list, whatever its name; `__dunder__` functions and `@knot`
  factories are the only structural exemptions.
- Adding to the allowlist is a reviewed decision, not a convenience: the function must be a
  documented public entry point (an ambient accessor, a driver, or a decorator that cannot be
  a method). Private helpers, CLI `main`s and thin wrappers over a class method are never
  allowlisted — they become static methods.
- A public name that predates the rule stays importable as a bare alias to the static method
  (`content_hash = _ContentHasher.hash`, `load_pipeline = PipelineLoader.load_yaml`). An alias
  is an assignment, not a `def`, so it is not counted — but do not add new bare aliases for new
  code; expose the class method.

#### No Nested Class/Function Definitions
- **NEVER nest class or function definitions** unless:
  1. It is a documented design decision
  2. It is marked with `# design-decision-override` comment
  3. It solves a specific scoping or closure problem that cannot be solved otherwise
- Define classes and functions at module level for testability and readability
- Use factories or partial functions instead of closures when state capture is needed

```python
# BAD - nested function (hard to test, unclear scope)
def process_data(data: list) -> list:
    def transform(item: int) -> int:
        return item * 2
    return [transform(x) for x in data]

# GOOD - module-level function (testable, clear scope)
def transform(item: int) -> int:
    return item * 2

def process_data(data: list) -> list:
    return [transform(x) for x in data]

# Acceptable - nested with explicit design decision override
def create_handler(config: dict):
    # design-decision-override: closure captures config without exposing it
    def handler(event: dict) -> None:
        if event["type"] in config["allowed_types"]:
            process_event(event, config["handler_type"])
    return handler
```

### Abstract Classes and Interfaces

Selected Style: **interface** — no `abc.ABC`, no `@abstractmethod`, and no
`typing.Protocol` for framework interfaces either. Every extension point in this
codebase (`Knot`, `DataTransport`, `IdentityResolver`, `Admission`, `Dispatcher`,
`Emitter`, `Trigger`, the backend base classes under `pirn/backends/base/`, and the
`FileFormat`/`BatchFileFormat`/`StreamingFileFormat` connector bases) is a plain base
class whose methods `raise NotImplementedError(...)`. See
`docs/architecture/extension-points.md` for the real ones; the example below is generic.

#### Using Interface Pattern (Traditional OOP Interfaces)
- Interfaces are base classes with standard `__init__` containing base details repeated across classes
- Interface methods raise `NotImplementedError` for methods that must be implemented by subclasses
- Used as roots of inheritance trees to define contracts through inheritance
- Provides clear inheritance hierarchies and explicit contracts
- Better for internal APIs where inheritance is expected

```python
class Repository:
    """Interface for repository implementations.
    
    Base class providing common initialization and defining the interface
    that all repository implementations must follow.
    """
    
    def __init__(self, connection_string: str, timeout: int = 30):
        """Initialize repository with connection details.
        
        Args:
            connection_string: Database connection string
            timeout: Connection timeout in seconds
        """
        self.connection_string = connection_string
        self.timeout = timeout
    
    def get(self, id: str) -> Entity | None:
        """Retrieve entity by ID. Must be overridden by subclasses."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement get()")
    
    def save(self, entity: Entity) -> None:
        """Save entity to storage. Must be overridden by subclasses."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement save()")
    
    def delete(self, id: str) -> bool:
        """Delete entity by ID. Must be overridden by subclasses.""" 
        raise NotImplementedError(f"{self.__class__.__name__} must implement delete()")

# Implementation - explicit inheritance required
class SqlRepository(Repository):
    def __init__(self, connection_string: str, timeout: int = 30):
        super().__init__(connection_string, timeout)
        # Additional SQL-specific initialization
        self._engine = create_engine(connection_string)
    
    def get(self, id: str) -> Entity | None:
        return self._session.query(Entity).get(id)
    
    def save(self, entity: Entity) -> None:
        self._session.add(entity)
        self._session.commit()
    
    def delete(self, id: str) -> bool:
        entity = self.get(id)
        if entity:
            self._session.delete(entity)
            self._session.commit()
            return True
        return False

# Usage - inheritance provides the interface
def process_data(repo: Repository) -> None:
    entity = repo.get("123")
    if entity:
        repo.save(entity)
```

**When to use Interface pattern:**
- Creating base classes with shared initialization logic
- Building inheritance hierarchies for internal APIs
- When you want explicit contracts through inheritance
- For classes that will be instantiated and need base behavior
- When runtime type checking with inheritance is important
