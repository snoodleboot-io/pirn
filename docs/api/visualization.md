# Visualization

Render tapestries and run results as Mermaid diagrams or standalone HTML.

---

## `MermaidRenderer.for_tapestry()`

Generate Mermaid `graph LR` syntax showing the tapestry structure.

::: pirn.viz.mermaid_renderer.MermaidRenderer.for_tapestry
    options:
      show_source: false
      heading_level: 3

### Example

```python
from pirn.viz.mermaid_renderer import MermaidRenderer

# Embed in Markdown
print(MermaidRenderer.for_tapestry(tapestry))

# Write to a file for MkDocs
Path("docs/diagrams/pipeline.md").write_text(
    "```mermaid\n" + MermaidRenderer.for_tapestry(tapestry) + "\n```"
)
```

---

## `MermaidRenderer.for_run()`

Generate Mermaid syntax with knot outcomes overlaid via class assignments.

::: pirn.viz.mermaid_renderer.MermaidRenderer.for_run
    options:
      show_source: false
      heading_level: 3

### Example

```python
from pirn.viz.mermaid_renderer import MermaidRenderer

result = await tapestry.run(request)
diagram = MermaidRenderer.for_run(result)
```

Nodes are coloured: `ok` → green, `err` → red, `skipped` → grey.

---

## `TapestryHtmlRenderer.for_run()`

Generate a self-contained HTML file with SVG rendering, hover tooltips, and outcome filtering.

::: pirn.viz.tapestry_html_renderer.TapestryHtmlRenderer.for_run
    options:
      show_source: false
      heading_level: 3

### Example

```python
from pirn.viz.tapestry_html_renderer import TapestryHtmlRenderer
from pathlib import Path

result = await tapestry.run(request)
Path("run.html").write_text(TapestryHtmlRenderer.for_run(result))
```

The generated file has no external dependencies — open in any browser.

---

## `TapestryHtmlRenderer.for_tapestry()`

Generate a self-contained HTML file showing the tapestry structure without run outcomes.

::: pirn.viz.tapestry_html_renderer.TapestryHtmlRenderer.for_tapestry
    options:
      show_source: false
      heading_level: 3

---

## `pirn-explore` CLI

The `pirn-explore` command generates an interactive multi-tapestry explorer.

::: pirn.viz._explore_cli.ExploreCli
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
