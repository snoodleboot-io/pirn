# Visualization

Render tapestries and run results as Mermaid diagrams or standalone HTML.

---

## `mermaid_for_tapestry()`

Generate Mermaid `graph LR` syntax showing the tapestry structure.

::: pirn.viz.mermaid.mermaid_for_tapestry
    options:
      show_source: false
      heading_level: 3

### Example

```python
from pirn import mermaid_for_tapestry

# Embed in Markdown
print(mermaid_for_tapestry(tapestry))

# Write to a file for MkDocs
Path("docs/diagrams/pipeline.md").write_text(
    "```mermaid\n" + mermaid_for_tapestry(tapestry) + "\n```"
)
```

---

## `mermaid_for_run()`

Generate Mermaid syntax with knot outcomes overlaid via class assignments.

::: pirn.viz.mermaid.mermaid_for_run
    options:
      show_source: false
      heading_level: 3

### Example

```python
from pirn import mermaid_for_run

result = await tapestry.run(request)
diagram = mermaid_for_run(result)
```

Nodes are coloured: `ok` → green, `err` → red, `skipped` → grey.

---

## `html_for_run()`

Generate a self-contained HTML file with SVG rendering, hover tooltips, and outcome filtering.

::: pirn.viz.html.html_for_run
    options:
      show_source: false
      heading_level: 3

### Example

```python
from pirn import html_for_run
from pathlib import Path

result = await tapestry.run(request)
Path("run.html").write_text(html_for_run(result))
```

The generated file has no external dependencies — open in any browser.

---

## `html_for_tapestry()`

Generate a self-contained HTML file showing the tapestry structure without run outcomes.

::: pirn.viz.html.html_for_tapestry
    options:
      show_source: false
      heading_level: 3

---

## `pirn-explore` CLI

The `pirn-explore` command generates an interactive multi-tapestry explorer.

::: pirn.viz._explore_cli.main
    options:
      show_source: false
      heading_level: 3

### Usage

```bash
pirn-explore [folder] [--output FILE] [--no-open]
```

| Argument | Default | Description |
|----------|---------|-------------|
| `folder` | `.` | Directory to scan for pipeline definitions |
| `--output / -o` | `<folder>/pirn_explorer.html` | Output HTML file path |
| `--no-open` | — | Write file without opening browser |

The explorer includes: loom view (interactive DAG), tapestry list, execution history panel, knot detail panel with 7W provenance, and theme toggle.

**See also:** [Visualization Guide](../guides/visualization.md)
