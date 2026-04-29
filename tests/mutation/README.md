# Mutation tests

Reserved for mutation-testing artifacts produced by `mutmut`.

Phase 2 doesn't ship a curated mutation-test corpus yet. To run mutmut
against the codebase locally:

```
mutmut run --paths-to-mutate pirn/
mutmut results
```

The configuration in `pyproject.toml` covers the basics. A future phase
will pin a baseline mutation score and add custom mutators for
`pirn`-specific patterns (e.g. mutating `error_policy` constants).
