# YAML Loader

Load YAML pipeline definitions into live `Tapestry` objects.

---

## `load_pipeline()`

::: pirn.yaml_loader.loader.load_pipeline
    options:
      show_source: false
      heading_level: 3

### Quick example

```python
from pirn import load_pipeline, RunRequest

yaml_text = """
name: my_pipeline
nodes:
  - id: x
    type: parameter
    type_: int
  - id: doubled
    type: knot
    callable: double
    parents:
      x: x
"""

tapestry = load_pipeline(yaml_text, known_callables={"double": double})
result = await tapestry.run(RunRequest(parameters={"x": 5}))
```

---

## PipelineSpec

The root Pydantic model parsed from YAML.

::: pirn.yaml_loader.specs.pipeline_spec.PipelineSpec
    options:
      show_source: false
      members_order: source
      heading_level: 3

---

## Node specs

::: pirn.yaml_loader.specs.node_spec.NodeSpec
    options:
      show_source: false
      members_order: source
      heading_level: 3

::: pirn.yaml_loader.specs.parameter_spec.ParameterSpec
    options:
      show_source: false
      members_order: source
      heading_level: 3

::: pirn.yaml_loader.specs.knot_spec.KnotSpec
    options:
      show_source: false
      members_order: source
      heading_level: 3

::: pirn.yaml_loader.specs.source_spec.SourceSpec
    options:
      show_source: false
      members_order: source
      heading_level: 3

::: pirn.yaml_loader.specs.sink_spec.SinkSpec
    options:
      show_source: false
      members_order: source
      heading_level: 3

::: pirn.yaml_loader.specs.branch_spec.BranchSpec
    options:
      show_source: false
      members_order: source
      heading_level: 3

::: pirn.yaml_loader.specs.gate_spec.GateSpec
    options:
      show_source: false
      members_order: source
      heading_level: 3

::: pirn.yaml_loader.specs.map_spec.MapSpec
    options:
      show_source: false
      members_order: source
      heading_level: 3

::: pirn.yaml_loader.specs.reduce_spec.ReduceSpec
    options:
      show_source: false
      members_order: source
      heading_level: 3

::: pirn.yaml_loader.specs.aggregator_spec.AggregatorSpec
    options:
      show_source: false
      members_order: source
      heading_level: 3
