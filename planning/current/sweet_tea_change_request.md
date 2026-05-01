# Change Request: `sweet_tea.registry.Registry` cache staleness on parent-type lookups

**Date:** 2026-05-01
**Component:** `sweet_tea/registry.py`
**Severity:** Latent — bites only when `typed_entries(lookup_type=Parent)` is called *before* every `register(child_class, ...)` is finished, which is the exact pattern `AbstractFactory[Parent]` uses.
**Filed from:** pirn (`feat/domain-knot-libraries` branch) while wiring `KnotRegistry`/`AbstractFactory[Knot]`-style lookup against newly-defined `Knot` subclasses.

---

## Summary

`Registry.typed_entries(lookup_type=T)` memoises a filtered copy of `__registry` against `T` on first call. `Registry.register(class_def, …)` only refreshes the cache slot keyed by the **exact** `class_def`, never any parent-type slot in `__lookup`. As a result, classes registered after the first `typed_entries(T)` call are invisible to subsequent `typed_entries(T)` callers when `T` is an ancestor of the new class.

`AbstractFactory[T]` is the canonical sweet_tea consumer of that lookup, so this affects any abstract factory whose registrations and queries are interleaved.

---

## Concrete repro

```python
from sweet_tea.registry import Registry

class Animal: pass
class Dog(Animal): pass
class Cat(Animal): pass

# Step 1: query the abstract type before registrations.
#         AbstractFactory[Animal] would do this on its first .create() call,
#         and any has()/get_class()-style helper does it implicitly.
Registry.typed_entries(lookup_type=Animal)
# → []   (correct given the registry is empty)

# Step 2: register two Animal subclasses.
Registry.register("dog", Dog, library="pets")
Registry.register("cat", Cat, library="pets")

# Step 3: query again.
Registry.typed_entries(lookup_type=Animal)
# → []   ❌  expected [Entry("dog", Dog, ...), Entry("cat", Cat, ...)]

Registry.entries()
# → [Entry("dog", Dog, ...), Entry("cat", Cat, ...)]   (master list is correct)

Registry.typed_entries(lookup_type=Dog)
# → [Entry("dog", Dog, ...)]   (lookup-by-concrete works)
```

The second `typed_entries(Animal)` returns the cached empty list from step 1.

---

## Root cause

In `Registry.register(...)` (lines 109–115):

```python
with cls.__lock:
    if new_entry not in cls.__registry:
        cls.__registry.append(new_entry)

    if class_def in cls.__lookup:                 # ← only the exact class
        cls.__lookup[class_def].append(new_entry)
```

`__lookup` is keyed by lookup type. After step 1 above, `__lookup` contains `{Animal: []}`. When `Dog` is registered, `class_def is Dog`; `Dog not in __lookup`; the append guard skips. The `Animal` cache slot stays `[]` forever (or until process restart).

In `Registry.typed_entries(...)` (lines 75–87):

```python
if lookup_type not in cls.__lookup_keys:          # populate once
    cls.__lookup_keys.append(lookup_type)
    cls.__lookup[lookup_type] = [...]
return cls.__lookup[lookup_type].copy()           # else return cache
```

There is no invalidation hook — once a lookup type is seen, the cache it owns is authoritative for the rest of the process's lifetime.

---

## Why it matters

`AbstractFactory[T]` uses `typed_entries(lookup_type=T)` on every `create()` call. Any consumer that interleaves registration and resolution against the same `T` hits this. Common patterns that interleave:

- A registration helper that does `if not registry.has(name): register(...)` to be idempotent.
- A plugin loader that registers in batches with sanity checks between batches.
- Test setups that register fixtures, run an assertion, then register more fixtures.

Production code using `fill_registry()` at package import — followed by all factory queries afterwards — is not affected, because the first cached lookup occurs after registrations have completed.

---

## Proposed fixes

### Option A — invalidate on register

Clear the cache so the next `typed_entries(T)` re-derives from the master list.

```python
@classmethod
def register(cls, key, class_def, library="", label=""):
    new_entry = Entry(...)
    with cls.__lock:
        if new_entry not in cls.__registry:
            cls.__registry.append(new_entry)
            cls.__lookup.clear()
            cls.__lookup_keys.clear()
```

- **Pro:** smallest change; trivially correct; no MRO walk.
- **Con:** the next call to each previously-cached lookup type pays an O(N) re-derivation. Read-heavy callers who register rarely after warm-up are unaffected; callers that register frequently lose all cache benefit.

### Option B — refresh affected cache slots on register

Walk `__lookup_keys` and update every slot whose lookup type the new class belongs to.

```python
@classmethod
def register(cls, key, class_def, library="", label=""):
    new_entry = Entry(...)
    with cls.__lock:
        if new_entry not in cls.__registry:
            cls.__registry.append(new_entry)
            for lookup_type in cls.__lookup_keys:
                if lookup_type is Any or (
                    isinstance(lookup_type, type)
                    and issubclass(class_def, lookup_type)
                ):
                    cls.__lookup[lookup_type].append(new_entry)
```

- **Pro:** preserves the cache fast-path; correct under the same lifecycle assumptions the cache was designed around.
- **Con:** O(K) per register, where K is the number of distinct lookup types ever queried. Typically K is small (a handful of abstract base classes); the extra cost is cheap. Slight subtlety: must handle `Any` explicitly since `issubclass(class_def, Any)` raises.

### Recommendation

**Option B.** It preserves the read-side performance the cache exists for, and the per-register cost is bounded by the number of distinct abstract factory types in use, which is usually tiny. Option A is simpler but throws away the cache benefit on every register.

---

## Suggested tests

Add to `tests/test_registry.py` (or wherever Registry tests live):

```python
def test_typed_entries_sees_registrations_made_after_first_query():
    # The lifecycle that today fails.
    class Animal: pass
    class Dog(Animal): pass

    assert Registry.typed_entries(lookup_type=Animal) == []
    Registry.register("dog", Dog, library="pets")
    entries = Registry.typed_entries(lookup_type=Animal)
    assert any(e.class_def is Dog for e in entries)


def test_typed_entries_with_any_sees_late_registrations():
    class X: pass
    Registry.typed_entries(lookup_type=Any)   # prime the Any cache
    Registry.register("x", X, library="late")
    assert any(e.class_def is X for e in Registry.typed_entries(lookup_type=Any))


def test_typed_entries_does_not_double_count_on_re_register():
    class Y: pass
    Registry.register("y", Y, library="dup")
    Registry.register("y", Y, library="dup")  # same Entry — should dedupe
    same_entries = [e for e in Registry.typed_entries(lookup_type=Y) if e.class_def is Y]
    assert len(same_entries) == 1
```

(The third test guards Option B against the case where the registry skips an `if new_entry not in __registry` check while the cache update logic runs unconditionally.)

---

## Out of scope for sweet_tea but worth flagging in the same fix

The `Entry` dedup check in `register()` happens against `__registry` only:

```python
if new_entry not in cls.__registry:
    cls.__registry.append(new_entry)
```

Whichever fix lands should keep cache appends inside the same `if not duplicate:` branch so a re-register doesn't double-add to a cache slot.
