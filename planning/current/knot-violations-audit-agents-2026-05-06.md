# Knot Design Rules Audit Report

**Scan Date:** 2026-05-06  
**Method:** Automated AST scan, all rules R1-R11 + Security

## Legend

| Column | Rule | Details |
|--------|------|---------|
| R1 | `__init__` body is ONLY `super().__init__(...)` | No validation, assignments, or logic |
| R2 | Every `__init__` param (except `_config`, `**kwargs`) appears by same name in `process()` | Ensures direct testability |
| R3 | No `raise` statements in `__init__` | All validation deferred to `process()` |
| R4 | No `self._x` assignments storing inputs | Inputs arrive fresh in `process()` |
| R5 | No `@property` exposing stored inputs or derived strings | Computed values via private helpers only |
| R6 | Opaque resources use a dedicated vending Knot, not passed directly | Live connections/sessions cannot travel the graph |
| R7 | `__init__` params use Knot types or `Knot \| scalar` — NOT plain scalars | Ensures graph wiring and lineage |
| R8 | If inherits `SubTapestry`: `process()` calls `self._run_inner()` | N/A for plain `Knot`/`Source`/`Sink` |
| R9 | Quality assessment Knots returning `QualityReport` use `*Check` suffix, not `*Gate` | N/A if not a quality assessment Knot |
| R10-Algo | Module docstring contains `Algorithm:` section | Step-by-step description |
| R10-Math | Module docstring contains `Math:` section | Always required — N/A confirmed only after reading `process()` |
| R10-Refs | Module docstring contains `References:` section | N/A if entirely pirn-native |
| Sec | Any `hashlib.md5()` call includes `usedforsecurity=False` | N/A if no md5 usage |
| Step11 | Tests call `process()` directly with plain values under `tests/unit/` | Not just via Tapestry.run() |
| Step12 | All applicable rules pass AND Step11 passes | Ready for ruff/pyright/pytest |

**Cell values:** `[x]` = compliant · `[ ]` = violation · `N/A` = rule does not apply

---

## Audit Table

### Group 1 — control/handoff_check.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/control/handoff_check.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 2 — control/reflection_check.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/control/reflection_check.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 3 — control/safety_check.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/control/safety_check.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 4 — control/termination_check.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/control/termination_check.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 5 — generation/llm_call.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/generation/llm_call.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 6 — generation/output_parser.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/generation/output_parser.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 7 — generation/response_formatter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/generation/response_formatter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 8 — generation/streaming_llm_call.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/generation/streaming_llm_call.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 9 — input/context_builder.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/input/context_builder.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 10 — input/intent_classifier.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/input/intent_classifier.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 11 — input/message_parser.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/input/message_parser.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 12 — llm_provider_knot.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/llm_provider_knot.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 13 — memory/conversation_buffer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/memory/conversation_buffer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 14 — memory/memory_retriever.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/memory/memory_retriever.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 15 — memory/memory_writer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/memory/memory_writer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 16 — memory_store_knot.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/memory_store_knot.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 17 — planning/planner.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/planning/planner.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 18 — planning/tool_executor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/planning/tool_executor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 19 — planning/tool_result_aggregator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/planning/tool_result_aggregator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 20 — planning/tool_router.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/planning/tool_router.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 21 — specializations/chain_of_thought

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/specializations/chain_of_thought/chain_of_thought.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/chain_of_thought/self_consistency_ensemble.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/chain_of_thought/step_back_prompting.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/chain_of_thought/tree_of_thought.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 22 — specializations/conversation

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/specializations/conversation/conversation_memory_pruner.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/conversation/multi_turn_context_assembler.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 23 — specializations/document_processing

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/specializations/document_processing/_chunk_embedder_store.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/document_processing/_chunk_translator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/document_processing/_document_chunker.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/document_processing/_document_loader.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/document_processing/_load_and_chunk.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/document_processing/_map_reduce_summariser.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/document_processing/_qa_load_and_chunk.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/document_processing/_qa_retrieve_and_answer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/document_processing/_translation_load_and_chunk.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/document_processing/document_ingestion_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/document_processing/document_qa_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/document_processing/document_summarizer_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/document_processing/document_translation_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/document_processing/embedding_indexer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/document_processing/metadata_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 24 — specializations/guardrails

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/specializations/guardrails/citation_grounder.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/guardrails/fact_check_gate.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/guardrails/fact_claim_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/guardrails/fact_claim_verifier.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/guardrails/hallucination_detector.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/guardrails/input_guardrail_gate.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/guardrails/input_message_scrubber.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/guardrails/output_guardrail_gate.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/guardrails/output_response_validator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/guardrails/pii_redactor_gate.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/guardrails/pii_response_redactor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 25 — specializations/human_in_the_loop

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/specializations/human_in_the_loop/approval_check.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/human_in_the_loop/clarification_requester.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/human_in_the_loop/escalation_router.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 26 — specializations/memory_patterns

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/specializations/memory_patterns/episodic_episode_writer.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/memory_patterns/episodic_memory_pipeline.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/memory_patterns/episodic_memory_retriever.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/memory_patterns/procedural_memory_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/memory_patterns/procedural_memory_writer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/memory_patterns/semantic_fact_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/memory_patterns/semantic_fact_writer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/memory_patterns/semantic_memory_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/memory_patterns/semantic_memory_upsert.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/memory_patterns/session_summarizer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/memory_patterns/working_memory_pipeline.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/memory_patterns/working_memory_window_writer.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 27 — specializations/multi_agent

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/specializations/multi_agent/consensus_aggregator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/multi_agent/consensus_majority_vote_picker.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/multi_agent/consensus_synthesis_caller.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/multi_agent/debate_framework.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/multi_agent/debate_judge.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/multi_agent/orchestrator_agent.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/multi_agent/orchestrator_router.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/multi_agent/parallel_specialist_fan_out.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/multi_agent/round_robin_review.py` (_ResponseEcho) | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/multi_agent/round_robin_review.py` (RoundRobinReview) | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/multi_agent/specialist_fan_out_collector.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [x] |

### Group 28 — specializations/plan_and_execute

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/specializations/plan_and_execute/plan_executor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/plan_and_execute/plan_revisor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/plan_and_execute/task_planner.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 29 — specializations/rag

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/specializations/rag/adaptive_rag_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/rag/corrective_rag_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/rag/corrective_router.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/rag/graph_rag_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/rag/hyde_rag_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/rag/llm_chat_call.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/rag/memory_search_retriever.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/rag/multi_hop_rag_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/rag/naive_rag_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/rag/rag_prompt_builder.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/rag/rag_response_builder.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/rag/rag_synthesizer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/rag/relevance_gate.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/rag/reranker.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/rag/self_rag_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/rag/sub_graph_context_builder.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 30 — specializations/react

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/specializations/react/messages_passthrough.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/react/react_loop.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/react/react_response_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/react/react_step_accumulator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/react/react_step_executor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/react/react_termination_check.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 31 — specializations/reflection

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/specializations/reflection/constitutional_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/reflection/outcome_simulator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/reflection/self_critique_revise.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 32 — specializations/routing

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/specializations/routing/capability_router.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/routing/confidence_router.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/routing/intent_router.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 33 — specializations/specialized_agents

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/specializations/specialized_agents/_analysis_step.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/specialized_agents/_code_generator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/specialized_agents/_code_linter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/specialized_agents/_code_response_formatter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/specialized_agents/_sql_executor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/specialized_agents/_sql_generator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/specialized_agents/_sql_response_formatter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/specialized_agents/browser_agent.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/specialized_agents/code_agent.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/specialized_agents/data_analyst_agent.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/specialized_agents/research_agent.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/specialized_agents/sql_agent.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 34 — specializations/structured_output

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/specializations/structured_output/_enum_classifier_attempt.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/structured_output/_json_extractor_attempt.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/structured_output/_llm_call_knot.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/structured_output/_yaml_extractor_attempt.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/structured_output/enum_classifier_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/structured_output/format_coercer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/structured_output/json_extractor_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/structured_output/pydantic_validator_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/structured_output/retry_on_parse_failure.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/structured_output/schema_enforcer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/structured_output/yaml_extractor_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 35 — specializations/tool_use

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/agents/specializations/tool_use/parallel_tool_caller.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/tool_use/tool_call_validator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/tool_use/tool_chain.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/tool_use/tool_result_formatter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
| `pirn/domains/agents/specializations/tool_use/tool_selector.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

