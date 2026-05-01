# Domain Knot Specializations Catalog

**Status:** Draft  
**Date:** 2026-04-30  
**Branch:** feat/domain-knot-libraries  
**Related:** domain-knot-libraries-prd.md, domain-knot-libraries-ard.md

This document enumerates the specific, concrete specializations for each domain library. These build on the generic knots defined in the PRD — many are SubTapestries composed from those generics.

**Total:** 469 specializations across seven domains  
**Key:** `K` = single Knot, `ST` = SubTapestry, `L` = LoopSubTapestry (iterative)

---

## Domain 1: `pirn.domains.data` — 53 Specializations

### Ingestion & Extraction (6)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `FullRefreshExtract` | K | Drops + fully reloads target from source on every run. No state or watermarks. |
| 2 | `WatermarkIncrementalExtract` | ST | Reads max `updated_at` from target, extracts only rows newer than that watermark, stores new high-water mark after each run. |
| 3 | `AppendOnlyIngest` | K | Inserts rows without ever updating/deleting. Assumes monotonically increasing keys. |
| 4 | `CDC_DebeziumConsumer` | ST | Reads Kafka topic from Debezium, parses op `c/u/d/r` envelope, routes inserts/updates/deletes to separate handlers and applies them in order. |
| 5 | `APIPagedExtract` | ST | Calls a paginated REST API repeatedly (cursor or offset/limit), accumulates all pages with backoff, yields a single combined dataset. |
| 6 | `PartitionedDateRangeExtract` | ST | Splits a date range into daily/hourly partitions, extracts each independently via `LoopSubTapestry`, enabling parallelism and partial retries. |

### Medallion Architecture (3)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 7 | `BronzeRawLanding` | K | Writes raw source data exactly as received with no transforms. Adds `_ingested_at` + `_source_system` metadata columns. Timestamped partition path. |
| 8 | `SilverCleansedLayer` | ST | `SchemaValidator` → `TypeCaster` → `NullHandler` → `Deduplicator` → `SilverSink` + `RejectSink`. Quarantines invalid rows. |
| 9 | `GoldAggregateLayer` | ST | `Join` → `BusinessLogicFilter` → `Aggregate` → `GoldSink`. Business-ready wide table for BI tools. |

### Slowly Changing Dimensions (8)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 10 | `SCD_Type0_Fixed` | ST | `LookupExisting` → `InsertIfNew` (Gate blocks any update). Written once at initial load, never updated regardless of source changes. |
| 11 | `SCD_Type1_Overwrite` | K | UPSERT: overwrites all attributes when natural key matches. No history retained. |
| 12 | `SCD_Type2_HistoryTracking` | ST | `LookupCurrentRow` → `DetectChanges` → `CloseOldRow` (set `valid_to`, `is_current=FALSE`) → `InsertNewRow` with surrogate key. Full history. |
| 13 | `SCD_Type2_HashDetect` | ST | Type 2 variant that computes a hash of all tracked columns rather than per-column comparison. Single hash diff replaces N column comparisons. |
| 14 | `SCD_Type3_PreviousValue` | K | Adds `{col}_previous` columns. Shifts current → previous on change. Retains one prior value only. |
| 15 | `SCD_Type4_MiniDimension` | ST | Splits rapidly-changing attrs into a separate mini-dim table. `MiniDimLookup` → Gate → `[reuse existing key | MiniDimInsert + new key]` → `FactKeyUpdater`. Main dim updated Type 1. |
| 16 | `SCD_Type5_MiniDimWithCurrent` | ST | Type 4 + denormalized `current_mini_dim_sk` on the main dimension. Analysts can get current state without joining through the fact table. |
| 17 | `SCD_Type6_Hybrid` | ST | Combines Type 1 + 2 + 3: full row history, current-value columns on all rows, and previous-value columns simultaneously. |
| 18 | `SCD_Type7_DualSurrogate` | ST | Stores both a `durable_sk` (stable for life of entity) and `current_sk` (latest Type 2 row) on every history row. `DurableKeyResolver` → expire old row → insert new row → backfill `current_sk` on all prior rows. |

### Dimensional Model Loading (4)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 19 | `DimTableLoad` | ST | Full dimension load: surrogate key generation → SCD logic (configurable Type 0–7) → write. Handles unknown (-1) and N/A (-2) default members. |
| 20 | `FactTableLoad` | ST | `SurrogateKeyLookup` (per dim) → `LateArrivingDimHandler` → `FactSink`. Resolves FK lookups, creates "unknown" placeholders for late dims. |
| 21 | `DateDimGenerator` | K | Generates a complete date dimension for a given date range: date_key (YYYYMMDD int), year/quarter/month/week/day, is_weekend, is_holiday, fiscal year. |
| 22 | `BridgeTableBuilder` | ST | Builds a many-to-many bridge table (customer↔segment) with weighting factors. Handles measure allocation across bridge rows. |

### Data Vault (5)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 23 | `DataVault_HubLoader` | K | Insert-only: loads new business keys into a Hub with hash key, load date, record source. Re-running with same keys is a no-op. |
| 24 | `DataVault_LinkLoader` | K | Insert-only: loads relationship rows into a Link (hash of all business keys + individual hub hashes). No updates ever. |
| 25 | `DataVault_SatelliteLoader` | K | Loads attributes into a Satellite: compares hash diff, inserts only changed rows. Tracks `load_date`, `load_end_date`, `hash_diff`, record source. |
| 26 | `DataVault_PITTableBuilder` | ST | Builds Point-In-Time table: one row per hub member per snapshot date, with pointer to the "as-of" satellite row for each satellite. Eliminates expensive range joins at query time. |
| 27 | `DataVault_BridgeTableBuilder` | ST | Flattens Link+Hub chains into a pre-joined flat FK structure — exposes Data Vault to BI tools expecting star schema. |

### Incremental & Snapshot Strategies (5)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 28 | `SnapshotTableAppender` | K | Appends a full dated snapshot of the source table to a history table on every run. Storage grows linearly with time. |
| 29 | `dbt_StyleSnapshot` | ST | `ComputeRowHash` → `LookupCurrentSnapshot` → `DetectChanges` → `CloseOldRows` → `InsertNewRows`. Implements dbt `timestamp`/`check` snapshot strategies. |
| 30 | `MergeUpsert` | K | Issues `MERGE` / `INSERT … ON CONFLICT DO UPDATE`. Inserts new, updates changed. No deletes. |
| 31 | `DeleteSafeSync` | ST | `ExtractSourceKeys` → `CompareKeysets` → `Upsert` → `SoftDelete`. Full sync with soft-delete (`is_deleted=TRUE`, `deleted_at=now()`). Never hard-deletes. |
| 32 | `PartitionedOverwrite` | K | Atomically overwrites a single partition of a partitioned table without touching other partitions. |

### Data Quality & Observability (7)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 33 | `RowCountAnomalyDetector` | K | Compares current run row count against rolling average of last N runs. Flags if deviation exceeds threshold (e.g. ±30%). |
| 34 | `NullRateMonitor` | K | Computes per-column null rate, compares against per-column thresholds, reports/fails on violations. |
| 35 | `SchemaEvolutionDetector` | K | Diffs incoming schema against registered expected schema. Detects added, dropped, and type-changed columns. Routes by policy (ignore/warn/fail). |
| 36 | `FreshnessCheck` | K | Queries max `updated_at` in target, compares to `now()`, fails if data older than SLA (e.g. "must be refreshed within 6 hours"). |
| 37 | `ReferentialIntegrityCheck` | K | Checks all FK values in a fact dataset have corresponding rows in the referenced dimension. Reports orphaned FK count and percentage. |
| 38 | `ReconciliationDiff` | ST | `HashRows(source)` → `HashRows(target)` → `OuterJoin` → `ClassifyRows` → `DiffReport`. Finds added, removed, and changed rows between two datasets. |
| 39 | `StatisticalProfiler` | K | Computes per-column: min, max, mean, median, stddev, p5/p25/p75/p95, cardinality, null rate, top-5 values. Stores profile for time-based drift comparison. |

### Deduplication (4)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 40 | `ExactDeduplicator` | K | Removes exact duplicates on key columns. Tiebreaker column + direction determines which row survives. |
| 41 | `WindowedDeduplicator` | K | Deduplicates within a time window: same key within N minutes = duplicate; same key after gap = legitimate new event. |
| 42 | `FuzzyDeduplicator` | ST | `Tokenizer` → `CandidatePairGenerator` (blocking) → `SimilarityScorer` (Levenshtein/Jaro-Winkler) → `ClusterAssigner`. Assigns cluster_id to near-duplicate groups. |
| 43 | `ProbabilisticLinker` | ST | Fellegi-Sunter record linkage: computes m/u probabilities per field, assigns match weights, classifies pairs as match/non-match/review. |

### Time Series & Analytics (6)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 44 | `TimeSeriesResampler` | K | Resamples a time series to a new frequency (tick→1min bars, hourly→daily). Configurable OHLC/sum/mean/last per column. Fills gaps with ffill/bfill/zero. |
| 45 | `RollingWindowAggregator` | K | Computes time-based rolling aggregates (7-day avg, 30-day sum, 90-day P95) respecting gaps in the series. |
| 46 | `SessionizationKnot` | K | Groups user event sequences into sessions by inactivity gap. Assigns session_id, computes session duration, event count, first/last event. |
| 47 | `FunnelAnalysisKnot` | K | For a defined event sequence (funnel), computes per-user stage reached, time between steps, conversion rates, and drop-off at each stage. |
| 48 | `CohortAggregator` | ST | `AssignCohort` → `ComputePeriod` → `AggregateByCohor​tPeriod` → `PivotTriangle`. Produces the classic cohort retention grid. |
| 49 | `LateArrivingEventHandler` | ST | `WatermarkCheck` → `Route(on-time/late)` → `LateEventSink` + `OnTimeProcessor` + `PartitionRecomputeTrigger`. |

### Feature Engineering for Data Pipelines (8)

These knots produce derived columns for downstream analytics — distinct from ML feature engineering (which lives in `pirn.domains.ml`) in that they operate on raw tabular data without a training/inference split and are designed for warehouse or lake environments.

| # | Name | Type | What it does |
|---|------|------|--------------|
| 50 | `DerivedColumnCalculator` | K | Evaluates expression-based derived columns (e.g. SQL-style expressions or callable) and appends them to the dataset. |
| 51 | `ColumnHasher` | K | Creates a deterministic hash of one or more columns. Used for surrogate key generation, row-level change detection, and PII tokenization. |
| 52 | `BinningKnot` | K | Buckets a continuous column into discrete bands (equal-width, equal-frequency/quantile, or custom breakpoints). |
| 53 | `StringNormalizer` | K | Standardizes string columns: trim whitespace, lowercase, strip accents, remove punctuation, collapse repeated spaces. |
| 54 | `DatePartExtractor` | K | Extracts date/time components (year, month, day, day-of-week, week-of-year, quarter, hour) as separate columns. |
| 55 | `GeoEnricher` | K | Joins a lat/lon or address column against a geo reference table to append region, city, country, and timezone. |
| 56 | `LookupEnricher` | K | Point-in-time lookup join against a slowly-changing reference dataset (e.g. map product_id → current category). Handles effective date semantics. |
| 57 | `TextTokenCounter` | K | Counts words, characters, sentences, and unique tokens in a text column. Useful for content profiling and downstream bucketing. |

### Analytics Engineering / dbt-Style (6)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 58 | `StagingModelKnot` | ST | `RawSourceRead` → `ColumnRenamer` → `TypeCaster` → `NullStandardizer` → `MetadataAdder` → `StagingSink`. One staging model per source table. |
| 59 | `IntermediateModelKnot` | ST | Joins + reshapes multiple staging models into a business-entity-shaped dataset. Not exposed to BI tools directly. |
| 60 | `MartModelKnot` | ST | Builds final BI-ready wide tables from intermediate models with final metric calculations. What Looker/Metabase queries. |
| 61 | `RefreshMaterializedView` | K | Triggers and awaits refresh of a database-native materialized view. Reports duration, rows affected, last refresh timestamp. |
| 62 | `MetricLayerAggregator` | ST | Computes a metric from a declarative definition (numerator/denominator/grain/dimensions). Equivalent to dbt Metrics / MetricFlow. |
| 63 | `ExposureLineageTag` | K | Records which dashboards/reports/apps consume a given table. Metadata-only — no data moved. Used for impact analysis. |

### Schema Evolution & Migration (3)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 64 | `BackfillRunner` | ST | `PartitionLister` → `Filter(unprocessed)` → `LoopSubTapestry(per partition)` → `BackfillManifestSink`. Resumable historical backfill for new columns or metrics. |
| 65 | `SchemaVersionMigrator` | ST | `VersionDetect` → `MigrationPlanSelector` → `MigrationApplier` → `SchemaValidator` → `MigratedSink`. Applies versioned schema migrations on read. |
| 66 | `ColumnLineageTracker` | K | Parses SQL/transform logic to extract column-level lineage edges (source col → target col, operation). Writes to metadata catalog. |

---

## Domain 2: `pirn.domains.agents` — 60 Specializations

### ReAct (Reason + Act) (3)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `ReActLoop` | ST | Canonical Reason+Act loop: LLM produces thought+action, action dispatched to tool, observation appended to context, repeats until `FINISH`. |
| 2 | `ThoughtScratchpad` | K | Prepends all prior `(Thought, Action, Observation)` triples into LLM context. Truncates oldest entries first on token budget. |
| 3 | `ActionParser` | K | Parses raw LLM output into structured `action_name` + `action_input`. Returns `FinishAction` sentinel when LLM signals done. |

### Chain-of-Thought Variants (4)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 4 | `ChainOfThought` | K | Wraps an LLM call with step-by-step reasoning elicitation. Optionally strips CoT from returned output, keeping only the answer. |
| 5 | `SelfConsistencyEnsemble` | ST | Runs N independent CoT samples in parallel (Map markers), aggregates by majority vote on final answer. |
| 6 | `TreeOfThought` | ST | Generates K candidate thoughts per step (BFS/DFS), scores/prunes with evaluator LLM, continues until terminal state or beam budget exhausted. |
| 7 | `StepBackPrompting` | K | First asks a high-level "step-back" abstraction question, then uses that principle as context for the original specific question. |

### Plan-and-Execute (3)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 8 | `TaskPlanner` | K | LLM call that decomposes a goal into an ordered list of `Task` objects with `id`, `description`, `depends_on`. |
| 9 | `PlanExecutor` | ST | Topologically sorts tasks, runs independent tasks concurrently via Aggregator, feeds results to dependent tasks. Re-plans on failure. |
| 10 | `PlanRevisor` | K | On task failure, calls LLM with original plan + completed results + failure reason to produce a revised remaining plan. |

### Reflection & Self-Critique (4)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 11 | `ReflectionGate` | K | Sends LLM output to a critic prompt. Below threshold → `GateClosed` to re-trigger generator. Above threshold → passes output through. |
| 12 | `SelfCritiqueRevise` | ST | Three-stage loop: generate → critique (LLM identifies flaws) → revise using critique as context. Repeats up to `max_rounds`. |
| 13 | `ConstitutionalFilter` | K | Applies a list of constitutional principles via critique-revision. Implements Anthropic's Constitutional AI step. |
| 14 | `OutcomeSimulator` | K | Before executing an action, calls LLM to simulate likely outcome and side-effects. Returns risk score + predicted outcome. |

### Multi-Agent (4)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 15 | `OrchestratorWorker` | ST | Orchestrator LLM decomposes task, dispatches to specialist workers (via Map or dynamic registration), aggregates and synthesizes results. |
| 16 | `AgentDebate` | ST | N LLM personas with opposing priors each generate a position, critique each other, judge LLM selects winner after N rounds. |
| 17 | `ParallelSpecialization` | ST | Routes same input to N specialist agents in parallel (legal, financial, technical), collects via Aggregator, synthesizes with general LLM. |
| 18 | `RoundRobinReview` | ST | Passes document sequentially through N reviewer agents, each reading prior annotations. Final reviewer consolidates. |

### RAG (Retrieval-Augmented Generation) (8)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 19 | `NaiveRAG` | ST | Embed query → retrieve top-k chunks → concatenate as context → LLM call with question+context. |
| 20 | `HypotheticalDocumentEmbedding` | ST | LLM generates a hypothetical answer to the query, embeds that answer (not the query) for retrieval. Improves recall for sparse queries. |
| 21 | `CorrectiveRAG` | ST | After retrieval, runs relevance evaluator per chunk. Below threshold → triggers web search to supplement. Combines internal + external sources. |
| 22 | `SelfRAG` | ST | LLM first decides retrieve/no-retrieve, retrieves, generates relevance + support tokens per chunk, selects best-supported generation. |
| 23 | `AdaptiveRAG` | ST | Routes by query complexity: direct LLM call (simple) → single-step RAG (moderate) → iterative multi-hop RAG (complex). |
| 24 | `MultiHopRAG` | ST | Iteratively retrieves: after each retrieval, LLM decides if answer found or generates sub-query for next hop. Up to `max_hops`. |
| 25 | `Reranker` | K | Re-scores retrieved chunks with a cross-encoder or LLM relevance scorer. Returns top-N sorted by relevance. |
| 26 | `RAGSynthesizer` | K | LLM call with chunks formatted as citations. Instructs inline citation of chunk IDs. Returns answer + citation map. |

### Memory (5)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 27 | `EpisodicMemoryWriter` | K | At turn end, summarizes exchange (intent, key facts, decisions) as a structured Episode record to a persistent store keyed by session ID. |
| 28 | `EpisodicMemoryRetriever` | K | Retrieves semantically relevant episodes from episodic store for injection into LLM context. |
| 29 | `SemanticMemoryUpsert` | K | Extracts factual statements from turn via LLM, deduplicates against existing semantic memory, upserts novel facts to vector store or knowledge graph. |
| 30 | `WorkingMemoryManager` | K | Bounded in-process scratchpad. Compresses oldest entries via LLM summarization when capacity exceeded. |
| 31 | `SessionSummarizer` | K | When history exceeds token threshold, LLM produces a rolling summary replacing raw history. Preserves key facts and decisions. |

### Tool Use (5)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 32 | `ToolSelector` | K | LLM (or classifier) selects tool name + populates arguments from a registry of tool schemas. Returns structured `ToolCall`. |
| 33 | `ParallelToolCaller` | ST | Fans out multiple `ToolCall`s concurrently via Map, collects via Aggregator, returns all results for next LLM turn. |
| 34 | `ToolChain` | ST | Executes a fixed sequence of tools where each output feeds the next. Sequential DAG of tool knots. |
| 35 | `ToolCallValidator` | K | Validates `ToolCall` arguments against tool JSON schema before execution. Returns `ValidationFailure` for LLM self-correction. |
| 36 | `ToolResultFormatter` | K | Formats raw tool output (dict, list, large blob) into token-efficient string for LLM context. Handles truncation and key extraction. |

### Guardrails (4)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 37 | `InputGuardrail` | K | Validates user input against policy: prompt injection, jailbreak, PII, off-topic. Returns `GateClosed` with violation reason on failure. |
| 38 | `OutputGuardrail` | K | Validates LLM output before returning to user: hallucinated links, toxicity, off-brand content, PII. Can suppress or redact. |
| 39 | `HallucinationDetector` | K | Checks each factual claim against source documents via NLI scoring. Returns grounding score + list of ungrounded claims. |
| 40 | `CitationGrounder` | K | Extracts cited sources from LLM output, verifies each appears in source documents. Flags fabricated citations. |

### Routing (3)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 41 | `IntentRouter` | K | Classifies input into intent categories (LLM zero-shot, few-shot, or fine-tuned), routes to specialist pipeline branch. |
| 42 | `ConfidenceRouter` | K | Lightweight LLM call produces answer + confidence score. Above threshold → fast path; below → expensive RAG + reflection path. |
| 43 | `CapabilityRouter` | K | Routes task to agent matching capability tags (code generation, data analysis, summarization). |

### Human-in-the-Loop (3)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 44 | `ApprovalGate` | K | Pauses pipeline, emits approval request (webhook/Slack/email). Blocks until approved/rejected. Timeout with auto-reject. |
| 45 | `ClarificationRequester` | K | When intent confidence is low, generates clarifying question, returns to user, awaits response before proceeding. |
| 46 | `EscalationRouter` | K | Detects human-intervention conditions (frustration, OOS requests, repeated failures, high stakes). Routes to human handoff branch with full context. |

### Structured Output (3)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 47 | `SchemaEnforcer` | K | LLM call with JSON schema injected into system prompt (or native structured output API). Validates response. Returns `ParseFailure` for retry. |
| 48 | `RetryOnParseFailure` | ST | Wraps structured output call in retry loop. On `ParseFailure`, formats error + malformed output into correction prompt and retries. Up to `max_retries`. |
| 49 | `FormatCoercer` | K | Deterministically coerces "almost valid" LLM output (single-quoted JSON, code block wrapping, trailing commas) into valid format before schema validation. |

### Document Processing (4)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 50 | `DocumentChunker` | K | Splits documents into chunks: fixed-size with overlap, sentence-boundary, semantic, or hierarchical (by section heading). Attaches position metadata. |
| 51 | `EmbeddingIndexer` | K | Batches chunks → embedding model → upserts vectors + metadata into vector store. Returns indexing stats. |
| 52 | `DocumentSummarizer` | ST | Map-reduce: split → parallel chunk summarization (LLM per chunk) → reduce chunk summaries into final summary. |
| 53 | `MetadataExtractor` | K | Structured LLM call over document: extracts title, authors, date, key topics, document type, named entities into `DocumentMetadata`. |

### Specialized Agent Types (5)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 54 | `SQLAgent` | ST | NL question → Text-to-SQL (LLM with schema context) → execute → interpret results in NL. Retry loop on SQL syntax errors. |
| 55 | `CodeAgent` | ST | Spec → generate code → execute in sandbox → capture stdout/stderr → iterate on errors. Stops on success or max attempts. |
| 56 | `ResearchAgent` | ST | Research question → iterative web search + retrieval + synthesis → generate follow-up queries → structured research report. |
| 57 | `DataAnalystAgent` | ST | Dataset + analytical question → plan analysis via LLM → write + execute Python/pandas → interpret results → generate charts + narrative. |
| 58 | `BrowserAgent` | ST | ReAct loop over browser: observe DOM → LLM decides action (click/type/scroll/extract) → execute → observe. Playwright/Selenium under the hood. |

### Conversation Management (2)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 59 | `MultiTurnContextAssembler` | K | Assembles full prompt: system prompt + compressed history summary + recent raw turns + current message. Enforces context window budget. |
| 60 | `ConversationMemoryPruner` | K | When buffer exceeds token threshold: removes oldest turns, summarizes removed portion into a single "memory" message. |

---

## Domain 3: `pirn.domains.ml` — 69 Specializations

### Experiment Patterns (11)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `BaselineEstablisher` | ST | Trains trivially-simple model (majority-class, mean predictor) and logs metrics as `EvalReport(baseline=True)` for comparison. |
| 2 | `AblationStudyPipeline` | ST | Runs `Trainer` N times with one feature group removed each time. Aggregates `EvalReport`s into ranked table of feature group contributions. |
| 3 | `ChampionChallengerGate` | K | Compares champion vs. challenger `EvalReport`s. Passes challenger downstream only if it exceeds champion by configured margin. |
| 4 | `KFoldCrossValidator` | ST | `CrossValidator(strategy="kfold")` + N parallel `Trainer` + `Evaluator` runs + aggregator for mean/std of metrics across folds. |
| 5 | `StratifiedKFoldCrossValidator` | ST | Same as KFold but preserves class distribution in each fold. Required for imbalanced classification. |
| 6 | `TimeSeriesCrossValidator` | ST | Expanding-window or sliding-window CV where training data always precedes validation data in time. |
| 7 | `GroupKFoldCrossValidator` | ST | All samples from the same group (patient, store, user) stay together — never split across train/val. |
| 8 | `GridSearchTuner` | ST | Exhaustive Cartesian search over discrete parameter grid. Returns best params + all candidate scores. |
| 9 | `RandomSearchTuner` | ST | Samples N random combinations from parameter space. More efficient than grid for high-dimensional spaces. |
| 10 | `BayesianOptTuner` | ST | GP or TPE surrogate proposes next trial based on prior results. Efficient for expensive-to-evaluate models. |
| 11 | `HyperbandTuner` | ST | Successive halving: starts many configs with small resource budget, eliminates bottom half at each rung. |

### Feature Engineering (14)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 12 | `TargetEncoder` | K | Replaces each category with smoothed mean of target variable. Cross-fit smoothing prevents target leakage. |
| 13 | `FrequencyEncoder` | K | Replaces each category with its training-set frequency (count or proportion). |
| 14 | `HashEncoder` | K | Maps categories to a fixed-size binary space via hashing trick. Handles unseen categories at inference. |
| 15 | `LagFeatureGenerator` | K | Creates shifted column copies at lags [t-1, t-2, ..., t-n]. Respects time ordering. |
| 16 | `RollingStatisticsGenerator` | K | Computes rolling mean, std, min, max, skew over configurable windows per column. |
| 17 | `FourierFeatureGenerator` | K | Adds sine/cosine terms at multiple frequencies to encode cyclic patterns (hour, day, month). |
| 18 | `InteractionFeatureGenerator` | K | Creates pairwise product terms between specified column pairs. |
| 19 | `TFIDFExtractor` | K | Converts text column to sparse TF-IDF matrix with configurable vocab size, n-gram range, sublinear TF. |
| 20 | `TextEmbeddingExtractor` | K | Encodes text column into dense vectors via pluggable sentence transformer or API embedding model. Batches calls. |
| 21 | `ImageEmbeddingExtractor` | K | Extracts feature vectors from pre-trained CNN (ResNet, EfficientNet, CLIP) penultimate layer. Loads images from path column. |
| 22 | `FeatureStoreWriter` | K | Writes computed features to a feature store (Feast, Tecton, or `FeatureStoreProvider` protocol). Tags with entity keys + event timestamps. |
| 23 | `FeatureStoreReader` | K | Retrieves point-in-time correct feature snapshot for given entity keys. Handles time-travel semantics. |
| 24 | `GraphFeatureExtractor` | K | Computes graph-structural features (degree, PageRank, clustering coefficient, node2vec embeddings) and joins onto node-level dataset. |
| 25 | `NGramExtractor` | K | Extracts character or word n-grams from text column, optionally hashed to fixed-size space. |

### Training Patterns (10)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 26 | `EarlyStoppingTrainer` | K | Monitors validation metric, halts when it stops improving for `patience` epochs, restores best checkpoint. |
| 27 | `LRSchedulerTrainer` | K | Wraps neural network `Trainer` with declarative LR schedule (cosine annealing, step decay, warmup+decay). |
| 28 | `BaggingEnsembleBuilder` | ST | Trains N `Trainer` instances on bootstrap samples. Aggregates by majority vote (classification) or mean (regression). |
| 29 | `StackingEnsembleBuilder` | ST | Trains diverse base learners on cross-validated OOF predictions, trains meta-learner on stacked OOF. |
| 30 | `BlendingEnsembleBuilder` | ST | Trains N base learners, combines predictions on held-out blend set using learned weighting. Faster than stacking. |
| 31 | `FineTuningTrainer` | K | Loads pretrained checkpoint, unfreezes selected layers, continues training with lower LR on domain-specific data. |
| 32 | `FeatureExtractionTransferTrainer` | K | Freezes all pretrained layers, only trains a new classification head appended to the frozen backbone. |
| 33 | `OnlineLearnerTrainer` | K | Wraps a `partial_fit`-compatible estimator. Accepts mini-batches sequentially without full retraining. |
| 34 | `SemiSupervisedTrainer` | ST | Train on labeled data → pseudo-label high-confidence unlabeled samples → augment labeled set → retrain. Repeat K iterations. |
| 35 | `SelfSupervisedPretrainer` | ST | Trains encoder on self-supervised pretext task (masked prediction, contrastive similarity) on unlabeled data. |

### Evaluation Patterns (12)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 36 | `ThresholdOptimizer` | K | Sweeps decision threshold 0→1, selects threshold optimizing target metric. Supports precision-at-recall constraints. |
| 37 | `CalibrationFitter` | K | Fits Platt scaling or isotonic regression on validation set. Produces reliability diagram + ECE score. |
| 38 | `ROCAUCAnalyzer` | K | Computes full ROC curves and AUC for binary/multi-class settings. Supports champion vs. challenger comparison. |
| 39 | `ConfusionMatrixAnalyzer` | K | Per-class precision, recall, F1, support. Flags classes below per-class performance threshold. |
| 40 | `ResidualAnalyzer` | K | Computes residuals, checks for heteroskedasticity, bias by feature quintile, and outlier residuals. |
| 41 | `PredictionIntervalEstimator` | K | Conformal prediction or quantile regression intervals at a specified coverage level. Outputs empirical coverage on holdout. |
| 42 | `WalkForwardValidator` | ST | Simulates live deployment: for each window, train on prior data, predict for window, compute metrics, advance. Produces metric time series. |
| 43 | `BacktestingEvaluator` | ST | Walk-forward for financial/trading strategies. Computes Sharpe ratio, max drawdown, equity curve, trade-level breakdown. |
| 44 | `RankingEvaluator` | K | Evaluates learning-to-rank with NDCG@K, MAP, MRR, precision@K. Groups by query ID before computing per-query metrics. |
| 45 | `NLGEvaluator` | K | Computes BLEU, ROUGE-L, BERTScore, METEOR for text generation. Handles multiple reference translations. |
| 46 | `FairnessAuditor` | K | Computes demographic parity, equalized odds, equal opportunity, individual fairness across sensitive attribute slices. |
| 47 | `AdversarialRobustnessEvaluator` | ST | Generates adversarial examples (FGSM, PGD, feature perturbation), measures metric degradation vs. clean examples. |

### Production / MLOps Patterns (11)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 48 | `ModelLineageTracker` | K | Records full `TrainedModel` provenance — data sources, features, hyperparams, metrics, parent experiment — to a `LineageStore`. |
| 49 | `ShadowModeDeployer` | ST | Routes production requests to both champion and challenger simultaneously. Champion served to users; both logged for comparison. |
| 50 | `CanaryDeployer` | ST | Routes configurable fraction of traffic to challenger. Monitors error rate and metric divergence; auto-rolls back on threshold breach. |
| 51 | `ABTestDeployer` | ST | Deterministic user assignment (hash-based) to control/treatment. Accumulates outcomes, runs statistical test, declares winner at min sample size. |
| 52 | `DataDriftDetector` | K | Compares feature distribution of recent production data vs. training baseline via PSI/KS/chi-square. Gates downstream on drift. |
| 53 | `ConceptDriftDetector` | K | Monitors prediction error distribution over time via ADWIN/Page-Hinkley/DDM. Signals when feature→label relationship has changed. |
| 54 | `PredictionDriftMonitor` | K | Tracks output score distribution over time. Alerts on output distribution shift before ground truth labels are available. |
| 55 | `PerformanceTriggeredRetrainer` | ST | Monitors live eval metrics. When a metric falls below floor, triggers full retraining SubTapestry → MetricGate → registration. |
| 56 | `BatchInferencePipeline` | ST | Load model from registry → apply feature transforms → run `Predictor` over large dataset in chunks → write to sink. |
| 57 | `SHAPExplainer` | K | Computes SHAP values via TreeExplainer or KernelExplainer. Aggregates global feature importance. |
| 58 | `LIMEExplainer` | K | Fits local linear surrogate around each prediction instance via input perturbation. Per-instance feature weights. |

### Task-Specific Pipelines (11)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 59 | `BinaryClassificationPipeline` | ST | Full pipeline: stratified split → feature prep → feature selection → hyperparameter search → evaluate → threshold optimize → calibrate → fairness audit → register. |
| 60 | `RegressionPipeline` | ST | Full pipeline: split → feature prep → hyperparameter search → evaluate (RMSE/MAE/R2) → residual analysis → prediction intervals → gate → register. |
| 61 | `TimeSeriesForecastingPipeline` | ST | Lag + rolling stat + Fourier features → time series CV → train → walk-forward validation → gate (MAPE/RMSE/SMAPE) → register. |
| 62 | `AnomalyDetectionPipeline` | ST | Scale → train (IsolationForest/AutoEncoder/LOF) → threshold optimize (if labels available) → evaluate → register. |
| 63 | `CollaborativeFilteringPipeline` | ST | User-item interactions → matrix construction → train (ALS/SVD/NMF) → ranking evaluation (NDCG@10/MAP) → gate → register. |
| 64 | `TextClassificationPipeline` | ST | TF-IDF or embedding vectorization → stratified k-fold CV → train → evaluate → confusion matrix → gate → register. |
| 65 | `NamedEntityRecognitionPipeline` | ST | Token-sequence data → fine-tune BERT/RoBERTa → evaluate with span-level NER metrics → gate → register. |
| 66 | `ImageClassificationPipeline` | ST | Image embeddings or full fine-tune → stratified k-fold → evaluate (top-1/top-5 acc, per-class F1) → gate → register. |
| 67 | `ClusteringPipeline` | ST | Scale → optional UMAP reduction → train (KMeans/HDBSCAN/GMM) → evaluate (silhouette/Davies-Bouldin) → register cluster assignments. |
| 68 | `DimensionalityReductionPipeline` | ST | Scale → train (PCA/UMAP/tSNE) → evaluate (explained variance, trustworthiness, continuity) → serialize fitted reducer. |
| 69 | `ActiveLearningLoop` | L | Train on seed → predict on unlabeled pool → query strategy selects informative samples → oracle labels → augment → retrain. Repeat until budget exhausted. |

---

## Additional Data Contracts Needed

These extend the types defined in the PRD.

### `pirn.domains.data.types`
- `RunManifest` — partition-level progress for `BackfillRunner`
- `SchemaDiff` — added/removed/changed columns from `SchemaEvolutionDetector`
- `DiffReport` — added/removed/changed row counts from `ReconciliationDiff`
- `ColumnProfile` — per-column statistics from `StatisticalProfiler`
- `MatchPair` — scored record pair from `FuzzyDeduplicator` / `ProbabilisticLinker`

### `pirn.domains.agents.types`
- `ReActStep` — `(thought, action, observation)` triple
- `ThoughtNode` — node in Tree of Thought search tree
- `Task` — `{id, description, depends_on}` from `TaskPlanner`
- `Episode` — structured episodic memory record
- `Source` — retrieval source with URL, text, and relevance score

### `pirn.domains.ml.types`
- `CrossValReport` — per-fold + aggregated mean/std metrics
- `AblationReport` — feature group → metric delta table
- `TuningReport` — candidate hyperparams + scores, convergence curve
- `ThresholdReport` — threshold sweep curve + optimal threshold + metric value
- `CalibrationReport` — reliability diagram + ECE score
- `ResidualReport` — residual distribution, bias-by-feature, outlier indices
- `DriftReport` — per-feature drift scores + drift flag + change point timestamp
- `FairnessReport` — per-slice metrics, disparity ratios, violation flags
- `RobustnessReport` — clean vs. adversarial metric delta
- `ExplainabilityReport` — per-sample SHAP/LIME values + global importance
- `ShadowLog` — champion/challenger prediction pairs with metadata
- `CanaryReport` — traffic split percentages, metric comparison, rollback events
- `ABTestReport` — group metrics, p-value, confidence intervals, declared winner
- `WalkForwardReport` — per-window metric time series + degradation trend
- `BacktestReport` — equity curve, Sharpe ratio, max drawdown, trade breakdown
- `IntervalReport` — prediction interval bounds + empirical coverage on holdout

## Additional Protocols Needed

### `pirn.domains.ml.protocols`
- `LineageStore` — for `ModelLineageTracker`
- `FeatureStoreProvider` — for `FeatureStoreReader` / `FeatureStoreWriter`
- `EmbeddingProvider` — for `TextEmbeddingExtractor`
- `ImageEncoderProvider` — for `ImageEmbeddingExtractor`

---

## Domain 4: `pirn.domains.connectors` — 50 Connectors

A separate library from `pirn.domains.data`. Connectors are infrastructure concerns (auth, wire protocols, pagination) and have independent release cadence and dependency surfaces. Users install only what they need: `pip install pirn-connectors[postgres,s3,kafka]`.

**Architecture:** Each connector family has an abstract base class (`DatabaseSource`, `ObjectStorageSource`, `ApiSource`, `StreamingSource`) plus concrete implementations. A `FileFormat` protocol (`read(path)`, `write(path, data)`) is accepted as a parameter by storage connectors — avoiding a combinatorial explosion of `S3ParquetSource`, `S3CSVSource`, etc.

**Note:** pirn already has backends for Postgres, SQLite, Valkey, DuckDB, S3, GCS, and Azure Blob as *state stores*. These connectors are distinct — they move *business data* through pipelines, not framework state.

### Databases & Warehouses (11)

| Connector | Role | Key Config | Notes |
|-----------|------|-----------|-------|
| `PostgresConnector` | Source + Sink | `dsn`, `schema`, `ssl_mode` | `COPY` protocol for bulk loads; asyncpg driver |
| `MySQLConnector` | Source + Sink | `host`, `port`, `database`, `user`, `password`, `charset` | `LOAD DATA INFILE` for bulk; aiomysql/asyncmy |
| `SQLiteConnector` | Source + Sink | `path`, `timeout` | WAL mode for concurrent reads; local dev + testing |
| `BigQueryConnector` | Source + Sink | `project`, `dataset`, `credentials`, `location`, `write_disposition` | Storage Write API for streaming; Storage Read API for exports; partition filter required for cost control |
| `SnowflakeConnector` | Source + Sink | `account`, `warehouse`, `database`, `schema`, `role`, `authenticator` | Synchronous driver — wrapped in `asyncio.to_thread`; `COPY INTO` stage for bulk loads |
| `RedshiftConnector` | Source + Sink | `host`, `database`, `user`, `password`, `iam_role` | PostgreSQL wire protocol; `COPY … FROM 's3://…'` for bulk; needs `VACUUM`/`ANALYZE` after large loads |
| `DuckDBConnector` | Source + Sink | `path` (`:memory:` or file), `read_only` | Native Parquet/CSV/JSON/Arrow reading; single-process; excellent for local transforms before shipping |
| `ClickHouseConnector` | Source + Sink | `host`, `port`, `database`, `user`, `password`, `compression` | `clickhouse-connect` (HTTP) or `asynch` (native); ReplacingMergeTree for upsert semantics |
| `DatabricksConnector` | Source + Sink | `server_hostname`, `http_path`, `access_token`, `catalog`, `schema` | Delta Lake merge for upserts; Unity Catalog; cluster cold-start latency |
| `MSSQLConnector` | Source + Sink | `server`, `database`, `user`, `password`, `driver` | `BULK INSERT` / BCP for loads; Azure SQL uses Entra ID token auth |
| `OracleConnector` | Source + Sink | `dsn`, `user`, `password` | `python-oracledb` thin mode; sequences for surrogate keys; thread pool for async |

### Object Storage & File Systems (5)

| Connector | Role | Key Config | Notes |
|-----------|------|-----------|-------|
| `S3Connector` | Source + Sink | `bucket`, `key`/`prefix`, `region`, `endpoint_url` | aioboto3; multipart upload >100 MB; S3-compatible (MinIO, Ceph) via `endpoint_url` |
| `GCSConnector` | Source + Sink | `bucket`, `blob`/`prefix`, `project`, `credentials` | `gcsfs`; resumable uploads; HMAC keys for S3-compatible access |
| `AzureBlobConnector` | Source + Sink | `account_name`, `container`, `connection_string`/managed identity | Async `BlobServiceClient`; ADLS Gen2 hierarchical namespace is a different API surface |
| `LocalFilesystemConnector` | Source + Sink | `path`, `glob_pattern`, `encoding` | `aiofiles`; atomic writes (temp + rename); glob patterns for directory Sources |
| `HDFSConnector` | Source + Sink | `namenode_host`, `namenode_port`, `user`, `path` | `pyarrow` HDFS bindings or WebHDFS REST; primarily on-premise Hadoop |

### File Formats (7) — Protocol Handlers, Not Standalone Knots

Consumed as `format: FileFormat` parameter by storage connectors.

| Format | Read | Write | Notes |
|--------|------|-------|-------|
| `CSVFormat` | ✓ | ✓ | Delimiter inference, encoding detection, null representation config |
| `ParquetFormat` | ✓ | ✓ | Predicate pushdown; row group size; partition pruning |
| `JSONLFormat` | ✓ | ✓ | Newline-delimited; streaming-friendly; `orjson` for performance |
| `JSONFormat` | ✓ | ✓ | Entire file is one object; not suitable for large datasets |
| `AvroFormat` | ✓ | ✓ | Schema-embedded; `fastavro`; Schema Registry integration for Kafka |
| `DeltaLakeFormat` | ✓ | ✓ | Parquet + transaction log; `delta-rs`; time travel; change data feed for incremental |
| `IcebergFormat` | ✓ | ✓ | `pyiceberg`; REST catalog; partition evolution; schema evolution; multi-engine |

### Streaming & Messaging (6)

| Connector | Role | Key Config | Notes |
|-----------|------|-----------|-------|
| `KafkaConnector` | Source + Sink | `bootstrap_servers`, `topic`, `group_id`, `security_protocol`, `schema_registry_url` | `confluent-kafka` or `aiokafka`; exactly-once requires idempotent producer + transactions; pirn already has Kafka trigger/emitter — this is the data-movement variant |
| `KinesisConnector` | Source + Sink | `stream_name`, `region`, `starting_position` | aioboto3; 1 MB/s per shard write; Enhanced Fan-Out for dedicated read throughput |
| `PubSubConnector` | Source + Sink | `project`, `topic` (Sink), `subscription` (Source), `credentials` | `google-cloud-pubsub` async; push vs pull; ordering keys for ordered delivery |
| `RabbitMQConnector` | Source + Sink | `host`, `vhost`, `user`, `password`, `queue`/`exchange`, `routing_key` | `aio-pika`; prefetch count for backpressure; publisher confirms for reliable Sink |
| `AzureServiceBusConnector` | Source + Sink | `connection_string`/managed identity, `queue_name`/`topic_name` | `azure-servicebus` async; sessions for ordered delivery; dead-letter queues |
| `ValkeyStreamConnector` | Source + Sink | `host`, `port`, `stream_key`, `consumer_group`, `consumer_name` | `valkey-py`; `XADD` Sink / `XREADGROUP` Source; `XACK` for explicit acknowledgment; extends pirn's existing Valkey backend |

### SaaS APIs (11)

All SaaS connectors implement: rate-limit token-bucket, pagination, configurable retry with exponential backoff, and a `ConnectionConfig` dataclass for credential injection from env vars / secrets manager.

| Connector | Role | Key Config | Notes |
|-----------|------|-----------|-------|
| `SalesforceConnector` | Source + Sink | `instance_url`, `client_id`, `client_secret` / JWT | Bulk API 2.0 for >50k records; SOQL for queries; sandbox vs production |
| `HubSpotConnector` | Source + Sink | `access_token` (Private Apps) | REST API v3; `after` cursor pagination; batch upsert for contacts/companies/deals |
| `StripeConnector` | Source | `api_key`, `webhook_secret` | Prefer webhook Source over polling; `starting_after` list pagination; idempotency keys |
| `GitHubConnector` | Source + Sink | `token`, `owner`, `repo` | REST v3 and GraphQL v4; `Link` header pagination; 5000 req/hr |
| `JiraConnector` | Source + Sink | `base_url`, `user_email`, `api_token` | JQL for queries; `startAt`/`maxResults` pagination; cloud vs server endpoint differences |
| `ShopifyConnector` | Source + Sink | `shop_domain`, `access_token`, `api_version` | Bulk Operations (GraphQL) for large exports; `page_info` cursor pagination |
| `GoogleAnalyticsConnector` | Source | `property_id`, `credentials` | GA4 Data API; dimensions/metrics model; sampling on large date ranges |
| `MixpanelConnector` | Source + Sink | `project_token`, `service_account_username/password` | `/import` endpoint for event ingestion (Sink); Export API for raw events (Source) |
| `AmplitudeConnector` | Source + Sink | `api_key`, `secret_key`, `server_url` | HTTP API v2 for event ingestion; Export API for raw data; 10 events/request recommended |
| `ZendeskConnector` | Source + Sink | `subdomain`, `email`, `api_token` | Incremental exports with `updated_at` cursor; `Retry-After` header; 700 req/min |
| `TwilioConnector` | Sink | `account_sid`, `auth_token`, `from_number` | SMS/voice/email (via SendGrid); webhook Source for inbound; E.164 number formatting |

### BI & Data Catalog (6)

| Connector | Role | Key Config | Notes |
|-----------|------|-----------|-------|
| `DbtArtifactsConnector` | Source | `artifacts_path`, `target` | Parses `manifest.json`, `run_results.json`, `catalog.json` for model metadata and test results |
| `FivetranConnector` | Source | `api_key`, `api_secret`, `connector_id` | Orchestrates Fivetran sync jobs from within a pirn pipeline; not a data-movement connector |
| `AirbyteConnector` | Source | `api_url`, `client_id`, `client_secret` | Triggers Airbyte sync jobs, polls status; OSS vs Cloud endpoint differences |
| `DataHubConnector` | Source + Sink | `gms_server_url`, `token` | `acryl-datahub` SDK; GraphQL reads; MCE/MCP writes for lineage emission |
| `OpenMetadataConnector` | Source + Sink | `host_port`, `jwt_token` | `openmetadata-ingestion`; auto-generate pipeline lineage from tapestry run metadata |
| `AlationConnector` | Source | `host`, `api_token` | Read catalog for governance metadata enrichment; limited write surface |

### Monitoring & Observability (4)

| Connector | Role | Key Config | Notes |
|-----------|------|-----------|-------|
| `DatadogConnector` | Sink | `api_key`, `site` | DogStatsD (UDP) for metrics; HTTP batch for logs; custom events for pipeline notifications |
| `PrometheusConnector` | Source + Sink | `pushgateway_url` / `prometheus_url` | Source: PromQL instant/range queries. Sink: push metrics to Pushgateway |
| `OpenTelemetryConnector` | Sink | `otlp_endpoint`, `service_name`, `headers` | OTLP gRPC or HTTP/protobuf; vendor-neutral — covers Datadog, Grafana, Jaeger, Honeycomb via one connector; **preferred over vendor-specific for new work** |
| `GrafanaConnector` | Sink | `prometheus_url`/`mimir_url`, `api_key` | remote_write to Grafana Mimir or Cloud; `prometheus-client` for metric definitions |

---

## Domain 5: `pirn.domains.health` — 82 Specializations

Healthcare pipelines handle regulated, high-stakes data across seven modalities. All knots surface `audit_log` metadata for HIPAA audit trails; PHI fields are marked in data contracts so downstream sinks can enforce field-level encryption.

### Clinical / EHR (18)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `FHIRPatientIngestor` | ST | Reads FHIR R4 Patient/Encounter/Observation/Condition bundles from REST API; paginates with `_count` + `_page`; validates resource schemas; yields `ClinicalRecord`. |
| 2 | `HL7v2MessageParser` | K | Parses HL7 v2.x ADT/ORU/ORM segments using python-hl7; emits typed segment dict with MSH, PID, PV1, OBX fields. |
| 3 | `OMOPCDMMapper` | ST | Maps FHIR resources or raw EHR tables to OMOP CDM v5.4 domains (person, visit_occurrence, condition_occurrence, measurement, drug_exposure). |
| 4 | `PHIRedactor` | K | Applies NER + regex to free-text fields; replaces 18 HIPAA Safe Harbor identifiers with type-tagged tokens (`[NAME]`, `[DATE]`, etc.); preserves clinical meaning. |
| 5 | `ICD10CodeValidator` | K | Validates ICD-10-CM/PCS codes against official code tables; flags invalid codes; optionally maps to ICD-9 via GEM crosswalk. |
| 6 | `SnomedCTNormalizer` | K | Maps clinical concept strings to SNOMED CT concept IDs via Athena/UMLS API or local Athena vocabulary download. |
| 7 | `RxNormNormalizer` | K | Normalizes medication names and NDC codes to RxNorm RxCUI identifiers; handles brand→generic mapping. |
| 8 | `LOINCMapper` | K | Maps lab test names/codes to LOINC identifiers; resolves component, method, and specimen axis. |
| 9 | `ClinicalNLPExtractor` | ST | Runs clinical NLP pipeline (MedSpaCy / cTAKES / AWS Comprehend Medical) on clinical notes; extracts entities: diagnoses, medications, procedures, negation status. |
| 10 | `MedicationReconciliationPipeline` | ST | Merges medication lists from multiple encounters; deduplicates by RxCUI; flags dose conflicts and discontinued medications. |
| 11 | `VitalSignsAggregator` | K | Groups time-series vitals (HR, BP, SpO2, temp) by patient/encounter; computes MEWS/NEWS early warning scores; flags out-of-range values. |
| 12 | `LabResultNormalizer` | K | Normalizes units (mg/dL → mmol/L etc.); applies reference-range flagging (L/H/Critical); resolves LOINC codes. |
| 13 | `DiagnosisCodeRollup` | K | Rolls ICD-10 codes up to configurable hierarchy level (3-char category, CCS grouper, Elixhauser comorbidity flag). |
| 14 | `ClinicalTrialEligibilityFilter` | ST | Applies inclusion/exclusion criteria expressed as structured predicates over OMOP data; returns eligible patient cohort. |
| 15 | `PatientCohortBuilder` | ST | Constructs a patient cohort from OMOP or FHIR using phenotype definition (index date, lookback/lookahead windows, entry criteria). |
| 16 | `EncounterTimelineAssembler` | ST | Joins patient events (admissions, labs, meds, procedures) onto a single chronological timeline per patient for ML feature construction. |
| 17 | `ClinicalDataQualityGate` | K | Checks missingness rates per field, date-range plausibility, duplicate encounter IDs, and referential integrity across OMOP tables. |
| 18 | `ReadmissionRiskScorer` | ST | Computes 30-day readmission risk using LACE/HOSPITAL score or a trained ML model; appends risk tier to patient record. |

### Genomics / Bioinformatics (19)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `FASTQQualityController` | ST | Runs FastQC or fastp on raw FASTQ files; emits per-base quality report; gates on per-base Q score < threshold. |
| 2 | `AdapterTrimmer` | K | Trims Illumina/Nextera adapter sequences using Trim Galore / Trimmomatic via subprocess wrapper; configurable min-length and quality cutoff. |
| 3 | `ReferenceGenomeAligner` | ST | Aligns FASTQ to reference genome (GRCh38/T2T) via BWA-MEM2 or STAR (RNA-seq); produces sorted, indexed BAM. |
| 4 | `BAMSortIndexer` | K | Sorts BAM by coordinate, marks duplicates (Picard MarkDuplicates), and indexes; emits `BAMFile` dataclass with path + stats. |
| 5 | `VariantCaller` | ST | Runs GATK HaplotypeCaller or DeepVariant; produces GVCF; supports WGS, WES, and amplicon modes with configurable interval lists. |
| 6 | `GVCFJointGenotyper` | ST | Combines per-sample GVCFs via GATK GenomicsDBImport + GenotypeGVCFs; emits cohort-level VCF. |
| 7 | `VCFQualityFilter` | K | Applies VQSR or hard-filter thresholds (QD, MQ, FS, SOR, MQRankSum, ReadPosRankSum) to emit PASS-only variants. |
| 8 | `VariantAnnotator` | ST | Annotates VCF with population frequencies (gnomAD), functional consequence (VEP/SnpEff), ClinVar pathogenicity, and CADD/REVEL scores. |
| 9 | `CNVCaller` | ST | Detects copy number variants using CNVkit or GATK ACNV; normalizes read depth; segments and calls CNV events. |
| 10 | `SVDetector` | ST | Detects structural variants (deletions, insertions, inversions, translocations) using MANTA or LUMPY; merges calls across tools. |
| 11 | `PharmacogenomicScorer` | K | Translates genotype calls to PharmGKB/CPIC diplotype → phenotype recommendations for star alleles (CYP2D6, CYP2C19, etc.). |
| 12 | `RNASeqQuantifier` | ST | Pseudo-aligns RNA-seq reads with Salmon/Kallisto; emits transcript-level TPM counts; aggregates to gene level via tximeta. |
| 13 | `DifferentialExpressionAnalyzer` | ST | Runs DESeq2 or edgeR via rpy2 on count matrix; emits `DEResult` with log2FC, p-value, FDR per gene. |
| 14 | `GeneSetEnrichmentRunner` | ST | Runs GSEA (pre-ranked) or ORA against MSigDB gene sets; emits enriched pathways with NES, FDR. |
| 15 | `SingleCellPreprocessor` | ST | Scanpy pipeline: QC filtering (min genes, max MT%), normalization (total count), log1p, HVG selection. |
| 16 | `SingleCellClusterer` | ST | PCA → neighbor graph (UMAP/tSNE) → Leiden/Louvain clustering; assigns cluster IDs to cells; emits AnnData. |
| 17 | `BulkATACSeqProcessor` | ST | Trims + aligns ATAC-seq reads; calls peaks with MACS3; generates consensus peak matrix; computes FRiP score. |
| 18 | `MethylationArrayProcessor` | ST | Processes Illumina EPIC/450k array IDAT files via minfi; normalizes (SWAN/Noob); emits β-value matrix; flags sex mismatches. |
| 19 | `MultiOmicsIntegrator` | ST | Integrates RNA-seq + ATAC-seq + methylation for matched samples using MOFA+ or Seurat WNN; emits joint embedding. |

### MRI / Neuroimaging (14)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `DICOMIngestor` | ST | Reads DICOM series from directory or PACS via pydicom; groups by SeriesInstanceUID; validates modality (MR/CT/PET); emits `DICOMSeries`. |
| 2 | `NIfTIConverter` | K | Converts DICOM series to NIfTI-1 via dcm2niix; preserves orientation metadata in JSON sidecar; validates orientation matrix. |
| 3 | `BIDSConverter` | ST | Organizes NIfTI + JSON sidecars into BIDS-compliant directory tree; validates against bids-validator; emits `BIDSDataset`. |
| 4 | `MRIQualityController` | K | Runs MRIQC image quality metrics (SNR, CNR, EFC, FBER); gates on configurable thresholds; flags motion artifacts. |
| 5 | `MRIPreprocessor` | ST | fMRIPrep-style preprocessing: realignment, slice-timing correction, fieldmap distortion correction, brain extraction, spatial normalization to MNI152. |
| 6 | `BrainExtractor` | K | Skull-stripping using FSL BET, HD-BET, or SynthStrip; emits brain mask + masked image. |
| 7 | `SpatialNormalizer` | ST | Registers subject-space image to MNI152 (or custom atlas) via ANTs SyN; applies forward/inverse transforms. |
| 8 | `CorticalThicknessEstimator` | ST | FreeSurfer `recon-all` pipeline; emits parcellated cortical thickness in Desikan-Killiany / Destrieux atlas. |
| 9 | `DTIPreprocessor` | ST | Eddy-current + motion correction (FSL eddy); tensor fitting; FA/MD/AD/RD map generation; tractography seed preparation. |
| 10 | `FunctionalConnectivityExtractor` | ST | Parcellates fMRI BOLD signal; computes functional connectivity matrix (Pearson / partial correlation / tangent); emits `ConnectivityMatrix`. |
| 11 | `TaskFMRIModeler` | ST | Convolves task onset files with HRF; runs GLM (Nilearn); emits contrast maps and design matrix summary. |
| 12 | `VBMMorphometryAnalyzer` | ST | Voxel-based morphometry: tissue segmentation (GM/WM/CSF via FSL FAST), smoothing, SPM/FSL GLM for group comparison. |
| 13 | `BrainAgeEstimator` | K | Runs pretrained brain age regression model on VBM/DL features; emits predicted age + brain age gap (BAG). |
| 14 | `LesionSegmenter` | K | Segments white matter lesions (MS plaques, stroke) using SAMSEG or LST; emits lesion mask + volume per region. |

### EEG / MEG (13)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `EEGRawIngestor` | K | Reads EEG/MEG files in EDF+, BrainVision, FIF, CNT formats via MNE-Python; validates channel labels against 10-20/10-10 montage; emits `RawEEG`. |
| 2 | `EEGMontageApplier` | K | Applies standard montage (10-20, 10-10, 10-05) or custom digitization; adds electrode 3D coordinates for source localization. |
| 3 | `EEGArtifactRejector` | ST | Detects and removes muscle, eye-blink, and channel-dropout artifacts; threshold + ICA-based (MNE ICA with EOG/ECG correlation); emits clean epochs. |
| 4 | `EEGICADecomposer` | ST | Runs ICA (FastICA or extended Infomax); auto-classifies components with ICLabel; removes eye/heart/muscle components; reconstructs signal. |
| 5 | `EEGBandpowerExtractor` | K | Computes absolute and relative band power (delta/theta/alpha/beta/gamma) per channel using Welch PSD; emits power spectral density matrix. |
| 6 | `EEGConnectivityAnalyzer` | K | Computes EEG connectivity metrics: coherence, phase-locking value (PLV), debiased WPLI, directed transfer function (DTF); emits connectivity matrix. |
| 7 | `EEGEpochExtractor` | K | Segments continuous EEG into epochs aligned to event triggers; applies baseline correction; rejects epochs by amplitude threshold. |
| 8 | `ERPAverager` | K | Averages epochs by condition to compute ERPs; emits grand average + per-subject averages with confidence intervals. |
| 9 | `MEGBeamformer` | ST | LCMV or DICS spatial filter for MEG source localization; beamforms power to cortical grid; emits source-space power map. |
| 10 | `MEGSourceLocalization` | ST | Dipole fitting or distributed MNE/dSPM/sLORETA source reconstruction; requires coregistered MRI; emits source time course. |
| 11 | `MEGTimeFrequencyAnalyzer` | K | Morlet wavelet or multitaper time-frequency decomposition; computes power and inter-trial coherence (ITC) per frequency band. |
| 12 | `SleepStageClassifier` | ST | Applies YASA or USLEEP model to PSG polysomnography data; outputs per-epoch sleep stages (W/N1/N2/N3/REM) and hypnogram. |
| 13 | `SeizureDetector` | ST | Real-time or offline seizure detection using line-length, spike detector, or deep learning (e.g., EEGNet); emits seizure onset/offset events with confidence. |

### Wearables & Biosignals (6)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `ECGRPeakDetector` | K | Pan-Tompkins or neurokit2 R-peak detection from ECG signal; computes RR intervals, heart rate, HRV metrics (RMSSD, SDNN, pNN50, LF/HF). |
| 2 | `AccelerometerActivityClassifier` | ST | Processes 3-axis accelerometer at ≥50 Hz; computes activity counts + ENMO; classifies activity bouts (sedentary/light/moderate/vigorous) using cut-point or ML model. |
| 3 | `PPGHeartRateExtractor` | K | Extracts heart rate and SpO2 from PPG waveform via peak detection; applies motion artifact rejection using accelerometer signal. |
| 4 | `CGMGlucoseAnalyzer` | K | Processes continuous glucose monitor data; computes time-in-range, glucose variability (CV%, GMI), MAGE, estimated A1C; flags hypoglycemic events. |
| 5 | `WearableSleepAnalyzer` | ST | Processes actigraphy (Philips Actiwatch / GeneActiv) using Cole-Kripke algorithm; estimates sleep onset, offset, WASO, sleep efficiency. |
| 6 | `SpirometryAnalyzer` | K | Parses spirometry flow-volume and time-volume curves; computes FVC, FEV1, FEV1/FVC, PEF; classifies obstruction pattern per ATS/ERS criteria. |

### Digital Pathology (5)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `WSITileExtractor` | ST | Opens whole-slide images (SVS, NDPI, SCN, MRXS) via OpenSlide; extracts non-overlapping or overlapping tiles at configured magnification and size; filters background tiles by tissue mask. |
| 2 | `PathologyStainNormalizer` | K | Normalizes H&E stain color variation using Macenko or Reinhard method; aligns to reference slide color profile. |
| 3 | `CellSegmenter` | ST | Nucleus detection + segmentation using StarDist or HoVer-Net; emits per-cell instance masks with centroid coordinates. |
| 4 | `TumorMicrobiotaClassifier` | ST | Runs tissue classification model (e.g., ResNet fine-tuned on TCGA WSIs) on tiles; aggregates tile predictions to slide-level diagnosis via attention-MIL. |
| 5 | `PathologyFeatureExtractor` | K | Extracts morphometric features per cell (size, shape, texture via GLCM, nuclear-to-cytoplasmic ratio); emits feature matrix for downstream ML. |

### Clinical Trials & Real-World Evidence (7)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `SDTMDomainValidator` | K | Validates CDISC SDTM domain datasets (DM, AE, CM, LB, VS, etc.) against define.xml and CDISC CT; emits conformance report. |
| 2 | `ADaMDatasetBuilder` | ST | Builds CDISC ADaM analysis datasets (ADSL, ADAE, ADLB, ADTTE) from SDTM inputs with traceability to source variables. |
| 3 | `SurvivalAnalysisPipeline` | ST | Kaplan-Meier curves, log-rank test, Cox proportional hazards model via lifelines; emits hazard ratios with CI, p-values, and survival curves. |
| 4 | `PropensityScoreMatcherPipeline` | ST | Logistic-regression propensity score estimation; 1:N nearest-neighbor or caliper matching; SMD balance assessment pre/post-match. |
| 5 | `RandomizedTrialAnalyzer` | ST | ITT + per-protocol analysis; handles missing data (LOCF, MMRM); computes primary endpoint with confidence interval and multiplicity adjustment. |
| 6 | `RWECohortExtractor` | ST | Extracts real-world evidence cohort from claims/EHR using index date logic, washout periods, and continuous enrollment criteria. |
| 7 | `EstimandAlignedAnalyzer` | ST | Implements ICH E9(R1) estimand framework: defines treatment policy / hypothetical / composite / principal stratum strategies; emits sensitivity analysis results. |

---

## Domain 6: `pirn.domains.signal` — 84 Specializations

Signal processing knots operate on `SignalFrame` (samples × channels, sample rate, metadata). All knots preserve `sample_rate` through the chain; frequency-domain knots return `SpectrumFrame`.

### Spectral Analysis (11)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `FFTAnalyzer` | K | Computes N-point FFT via NumPy/SciPy; applies zero-padding and windowing; returns two-sided or single-sided spectrum with frequency axis. |
| 2 | `IFFTReconstructor` | K | Inverse FFT from complex spectrum back to time domain; handles real-valued reconstruction with conjugate symmetry enforcement. |
| 3 | `STFTAnalyzer` | K | Short-Time Fourier Transform; configurable window (Hann/Hamming/Blackman), FFT size, and hop; emits spectrogram array (time × frequency). |
| 4 | `ISTFTReconstructor` | K | Inverse STFT with overlap-add reconstruction; Griffin-Lim iteration for magnitude-only spectrograms. |
| 5 | `WelchPSDEstimator` | K | Welch's method power spectral density; configurable window, nperseg, noverlap, detrend; emits PSD in V²/Hz. |
| 6 | `BartlettPSDEstimator` | K | Bartlett's method (non-overlapping segments averaged); lower spectral resolution than Welch, no spectral leakage between segments. |
| 7 | `MultitaperPSDEstimator` | K | Thomson multitaper PSD using DPSS tapers; superior frequency resolution + low spectral leakage; time-bandwidth product configurable. |
| 8 | `MelSpectrogramExtractor` | K | Applies Mel filterbank to STFT magnitude; log-compresses; emits mel-spectrogram for audio ML feature pipelines. |
| 9 | `MFCCExtractor` | K | Mel-frequency cepstral coefficients: STFT → Mel filterbank → log → DCT; emits N cepstral coefficients per frame. |
| 10 | `CepstralAnalyzer` | K | Real cepstrum (IFFT of log-magnitude spectrum); detects periodicity (pitch/echoes) via quefrency peaks; quefrency-domain liftering. |
| 11 | `HilbertTransformer` | K | Analytic signal via Hilbert transform; emits instantaneous amplitude (envelope) and instantaneous frequency/phase. |

### Filtering (17)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `ButterworthFilter` | K | Butterworth IIR filter (lowpass/highpass/bandpass/bandstop); configurable order and cutoff; maximally flat passband. |
| 2 | `ChebyshevType1Filter` | K | Chebyshev Type I IIR; steeper roll-off than Butterworth at cost of passband ripple; configurable ripple in dB. |
| 3 | `ChebyshevType2Filter` | K | Chebyshev Type II IIR; equiripple stopband, monotonic passband; sharper transition than Butterworth. |
| 4 | `EllipticFilter` | K | Elliptic (Cauer) IIR; minimum order for given spec; equiripple in both pass and stop bands; sharpest roll-off. |
| 5 | `BesselFilter` | K | Bessel/Thomson filter; maximally linear phase / constant group delay; preferred for waveform shape preservation. |
| 6 | `FIRWindowFilter` | K | FIR filter via window method (Hamming/Hann/Blackman/Kaiser); linear phase; configurable numtaps and window parameter. |
| 7 | `FIRParksMcClellanFilter` | K | Equiripple FIR via Parks-McClellan / Remez algorithm; optimal Chebyshev approximation; minimum-taps for given spec. |
| 8 | `MedianFilter` | K | Running median filter; nonlinear; excellent impulse/spike noise removal without blurring edges. |
| 9 | `SavitzkyGolayFilter` | K | Polynomial least-squares smoothing; preserves peak height and width; configurable window and polynomial order. |
| 10 | `WienerFilter` | K | Adaptive Wiener filter; minimum mean-square error estimation; requires noise PSD estimate; optimal linear denoiser. |
| 11 | `NotchFilter` | K | Sharp IIR notch (Twin-T or biquad); removes single frequency (power-line 50/60 Hz, etc.) with narrow stopband. |
| 12 | `CombFilter` | K | FIR/IIR comb filter; periodic frequency cancellation or reinforcement; configurable teeth spacing. |
| 13 | `AllpassFilter` | K | All-pass IIR; flat magnitude, configurable phase response; used for phase equalization and delay. |
| 14 | `ZeroPhaseFILter` | K | `filtfilt` forward-backward filtering; zero phase distortion; doubles effective filter order; noncausal. |
| 15 | `CausalRealTimeFilter` | K | `lfilter` with persistent state; causal and real-time safe; state carries over between calls for streaming use. |
| 16 | `BandpassFilterBank` | ST | Fan-out of `ButterworthFilter` or `FIRWindowFilter` nodes covering N frequency bands in parallel; outputs per-band `SignalFrame`. |
| 17 | `PolyphaseDecimator` | K | Polyphase FIR decimation by integer factor M; anti-alias filter baked in; efficient for large decimation ratios. |

### Wavelets (8)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `DWTDecomposer` | K | Discrete Wavelet Transform via PyWavelets; configurable wavelet family (Daubechies, Symlets, Coiflets, Biorthogonal) and decomposition levels. |
| 2 | `IDWTReconstructor` | K | Inverse DWT; reconstructs signal from approximation + detail coefficients; optional soft/hard thresholding before reconstruction. |
| 3 | `SWTDecomposer` | K | Stationary (undecimated) Wavelet Transform; translation-invariant; same number of coefficients at each level; used for denoising without Gibbs artifacts. |
| 4 | `WaveletDenoiser` | ST | DWT → threshold detail coefficients (VisuShrink/BayesShrink/universal) → IDWT; optimal for 1/f noise and broadband noise. |
| 5 | `CWTAnalyzer` | K | Continuous Wavelet Transform (Morlet, Mexican hat, Paul) via SciPy/PyWavelets; emits scalogram (scale × time) for time-frequency analysis. |
| 6 | `WaveletPacketDecomposer` | ST | Full wavelet packet tree decomposition; selects best basis via minimum entropy or minimum cost criterion; used for adaptive time-frequency tiling. |
| 7 | `EMDDecomposer` | ST | Empirical Mode Decomposition; iterative sifting to extract intrinsic mode functions (IMFs); no predefined basis; handles nonstationary signals. |
| 8 | `VMDDecomposer` | ST | Variational Mode Decomposition; solves constrained optimization for K band-limited IMFs; more robust than EMD for noise. |

### Adaptive Filtering (6)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `LMSAdaptiveFilter` | K | Least Mean Squares adaptive filter; gradient descent weight update; configurable step size µ and filter order; real-time noise cancellation. |
| 2 | `NLMSAdaptiveFilter` | K | Normalized LMS; step size normalized by input power; more stable convergence than LMS for varying signal levels. |
| 3 | `RLSAdaptiveFilter` | K | Recursive Least Squares; exponentially weighted least squares; faster convergence than LMS; configurable forgetting factor λ. |
| 4 | `ANCPipeline` | ST | Active Noise Control pipeline: reference microphone → LMS/NLMS adaptive filter → anti-noise generation → error microphone feedback loop. |
| 5 | `EchoCanceller` | ST | Acoustic echo cancellation: near-end microphone + far-end reference → NLMS/RLS adaptive filter → double-talk detector → residual echo suppressor. |
| 6 | `KalmanFilter` | K | Linear Kalman filter; configurable state transition, observation, process noise (Q), and measurement noise (R) matrices; optimal linear state estimator. |

### Statistical Signal Processing (7)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `ExtendedKalmanFilter` | K | EKF for nonlinear systems; first-order Taylor linearization at each step; configurable Jacobians for state and observation models. |
| 2 | `UnscentedKalmanFilter` | K | UKF using sigma-point (unscented) transform; better nonlinear approximation than EKF; no Jacobian required. |
| 3 | `ParticleFilter` | ST | Sequential Monte Carlo; configurable number of particles and resampling strategy (systematic/stratified/residual); handles multimodal posteriors. |
| 4 | `ARModelEstimator` | K | Autoregressive model parameter estimation via Yule-Walker equations or Burg's method; emits AR coefficients and model order selected by AIC/BIC. |
| 5 | `MUSICAlgorithm` | K | Multiple Signal Classification; eigendecomposition of covariance matrix; pseudospectrum peak picking for frequency/DOA estimation. |
| 6 | `ESPRITAlgorithm` | K | Estimation of Signal Parameters via Rotational Invariance; subspace rotation; direct frequency estimation without grid search. |
| 7 | `PISARENKOEstimator` | K | Pisarenko harmonic decomposition; minimum-eigenvalue signal model; estimates sinusoidal frequency and amplitude. |

### Source Separation & Decomposition (7)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `ICADecomposer` | ST | Independent Component Analysis (FastICA, Infomax, Picard) for BSS; estimates statistically independent sources from mixed observations. |
| 2 | `PCADecomposer` | K | Principal Component Analysis whitening + projection; decorrelates channels; useful for noise reduction and dimensionality reduction. |
| 3 | `NMFDecomposer` | ST | Non-negative Matrix Factorization on spectrogram; decomposes into non-negative basis spectra × activation patterns; audio source separation. |
| 4 | `BeamformerMVDR` | K | Minimum Variance Distortionless Response (Capon) beamformer; spatial filtering for multichannel array; maximizes SNR from target direction. |
| 5 | `BeamformerMUSIC` | K | MUSIC-based spatial spectrum beamformer; high-resolution direction-of-arrival estimation for sensor arrays. |
| 6 | `DelayAndSumBeamformer` | K | Classic delay-and-sum array processing; steers beam by applying per-channel time delays; computationally simple baseline. |
| 7 | `SSADecomposer` | ST | Singular Spectrum Analysis; trajectory matrix SVD → automatic or manual grouping of components → reconstruction; trend and periodicity extraction. |

### Nonlinear & Chaos Analysis (5)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `LyapunovExponentEstimator` | K | Estimates maximal Lyapunov exponent via Rosenstein algorithm; quantifies sensitivity to initial conditions (chaos indicator). |
| 2 | `SampleEntropyCalculator` | K | Sample entropy (SampEn): regularity/complexity metric for short time series; less biased than approximate entropy. |
| 3 | `PermutationEntropyCalculator` | K | Permutation entropy (PE): ordinal pattern distribution; computationally efficient nonlinear complexity measure. |
| 4 | `RecurrencePlotAnalyzer` | ST | Constructs recurrence matrix; computes RQA measures (RR, DET, LAM, ENTR, TT); detects regime changes and nonstationarities. |
| 5 | `HurstExponentEstimator` | K | Rescaled range (R/S) analysis or DFA for Hurst exponent H; characterizes long-range dependence and fractal scaling. |

### Resampling & Synchronization (7)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `RationalResamplerPipeline` | ST | Upsample by L → lowpass anti-aliasing filter → downsample by M; exact rational sample rate conversion. |
| 2 | `ArbitraryResamplerPipeline` | ST | Polyphase interpolation for arbitrary (non-rational) sample rate conversion; used when target rate is not a simple ratio of source. |
| 3 | `FractionalDelayFilter` | K | Allpass fractional delay using Thiran approximation or Lagrange interpolation; sub-sample time alignment. |
| 4 | `TimeSynchronizer` | ST | Cross-correlation time delay estimation between two signals; applies fractional delay to align; emits synchronized `SignalFrame` pair. |
| 5 | `ClockDriftCorrector` | ST | Estimates and corrects clock drift between recording channels using a shared reference signal; linear interpolation with drift model. |
| 6 | `MultiRateFusionPipeline` | ST | Fuses signals sampled at different rates (e.g., EEG at 1kHz + ECG at 256Hz): resample all to common rate → time-align → concatenate. |
| 7 | `StreamingBufferManager` | K | Manages overlapping frames for streaming processing: emits fixed-size windows with configurable hop, handling partial frames at boundaries. |

### Audio & Speech (8)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `AudioFileIngestor` | K | Reads WAV/MP3/FLAC/OGG via soundfile or librosa; resamples to target rate; emits `SignalFrame` with duration and channel metadata. |
| 2 | `VADDetector` | K | Voice Activity Detection (Silero VAD or WebRTC VAD); segments audio into speech/non-speech regions; emits segment list with timestamps. |
| 3 | `PitchEstimator` | K | Fundamental frequency (F0) estimation: YIN, pYIN, CREPE, or autocorrelation; voiced/unvoiced classification; emits F0 track with confidence. |
| 4 | `SpeakerDiarizationPipeline` | ST | Sliding window embeddings (ECAPA-TDNN) → clustering (AHC or spectral) → speaker label assignment per segment; emits RTTM-format diarization. |
| 5 | `AudioDenoiser` | ST | Spectral subtraction or deep learning (RNNoise, DeepFilterNet) noise suppression; estimates noise floor from VAD-detected silence segments. |
| 6 | `AudioAugmentationPipeline` | ST | Training data augmentation: time stretch, pitch shift, room impulse response convolution (RIR), SpecAugment (time/frequency masking). |
| 7 | `AudioFeatureExtractor` | K | Extracts frame-level features: MFCC, mel-spectrogram, chroma, spectral centroid/bandwidth/rolloff, zero-crossing rate; emits feature matrix. |
| 8 | `MusicInformationRetriever` | ST | Beat tracking (Librosa), chord estimation, key detection, onset detection; assembles MIR feature dict for music analysis or sync. |

---

## Domain 7: `pirn.domains.oilgas` — 63 Specializations

Oil & gas pipelines span seismic interpretation, petrophysical analysis, reservoir engineering, production operations, facilities integrity, and geospatial. All knots use `@dataclass` contracts; industry standards cited per knot. Stateful inner pipelines use `SubTapestry`.

### Seismic Data (13)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `SegyFileIngester` | K | Opens SEG-Y rev 0/1/2; reads 3200-byte EBCDIC + 400-byte binary headers; returns lazy trace iterator. Standards: SEG-Y rev 2 (2017). |
| 2 | `SegyTraceHeaderParser` | K | Decodes mandatory and optional byte-location trace header fields (CDP, inline, crossline, offset, coords) using user-supplied or standard byte-location map. |
| 3 | `SeismicQCGate` | K | Zero-trace detection, dead-trace flagging, RMS amplitude outlier check (±N sigma), sample count consistency, coordinate range validation. Raises on fatal; emits `QCWarning` list for soft failures. |
| 4 | `SphericalDivergenceGain` | K | Applies t² or user-defined spherical divergence correction to compensate amplitude decay with travel time; optional surface-consistent scalar. |
| 5 | `SeismicBandpassFilter` | K | Zero-phase Ormsby or Butterworth bandpass filter (f1/f2 low-cut, f3/f4 high-cut) via FFT; returns filtered trace and frequency spectrum. |
| 6 | `FKDenoisingKnot` | K | F-K (frequency-wavenumber) domain fan-shaped reject filter for coherent linear noise (ground roll, air wave) on common-shot or common-offset gathers. |
| 7 | `InstantaneousAttributeExtractor` | K | Hilbert transform → instantaneous amplitude (envelope), phase, frequency, and cosine of phase. DHI/bright-spot screening. Standards: Taner, Koehler & Sheriff (1979). |
| 8 | `RMSAmplitudeWindowExtractor` | K | Windowed RMS/peak/mean-abs amplitude extraction around a picked horizon (±N ms); outputs 2D amplitude map by inline/crossline. |
| 9 | `HorizonAutoPicker` | ST | Seed-pick loader → patch extractor → similarity tracker (normalized cross-correlation or semblance) → smoothing → export. Auto-tracks 3D seismic horizons from sparse seed picks. |
| 10 | `FaultDetectionKnot` | K | Edge-detection attributes (variance, coherence, curvature) + amplitude-gradient threshold; returns fault probability volume. Standards: Bahorich & Farmer (1995). |
| 11 | `AcousticImpedanceInverter` | ST | Wavelet estimator → low-freq model builder → sparse-spike inversion → post-conditioning. Post-stack acoustic impedance inversion from well-derived wavelet; outputs AI volume in g/cc × m/s. |
| 12 | `VelocityModelBuilder` | ST | Semblance scanner → velocity picker → Dix RMS-to-interval converter → smoothing. Builds interval velocity model for PSDM input and well depth prognosis. |
| 13 | `SubvolumeExtractor` | K | Streaming crop of a 3D SEG-Y volume to inline/crossline/time window with optional decimation; no full in-memory load. |

### Well Data (15)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `LasFileIngester` | K | Parses LAS 2.0/3.0 files: version/well/curve/parameter sections; decodes curve mnemonics, units, descriptions, and ASCII data table. Standards: CWLS LAS 2.0/3.0; OSDU Well Log Service. |
| 2 | `LogSpikeRemover` | K | Hampel identifier (median ± k×MAD window) spike detection per curve; fills removed values by linear interpolation or null; reports spike locations. Standards: API RP 45. |
| 3 | `DepthShiftCorrector` | K | Applies constant or depth-varying shift table (e.g., core-to-log or checkshot) and resamples curves to corrected depth grid. Standards: WITSML `DepthRegUnit`. |
| 4 | `EnvironmentalCorrectionApplicator` | K | Tool-specific borehole and mudcake corrections to resistivity, density, and neutron logs using chartbook lookup tables parameterized by hole size, mud weight, mud type, and tool model. |
| 5 | `VshaleCalculator` | K | Volume of shale from GR linear index, Larionov (Tertiary/old rocks), or neutron-density crossplot; returns minimum of selected methods. Standards: Larionov (1969). |
| 6 | `PorosityCalculator` | K | Total and effective porosity from density log (or neutron-density crossplot); corrects for shale content; optional gas correction. Standards: Wyllie; Gaymard & Poupon (1968). |
| 7 | `WaterSaturationCalculator` | K | Archie, Waxman-Smits, or Simandoux Sw from Rt, Rw, porosity, and cementation/saturation exponents. Standards: Archie (1942); Waxman & Smits (1968). |
| 8 | `PermeabilityEstimator` | K | Empirical transforms (Timur, Coates-Dumanoir, Kozeny-Carman) from porosity and irreducible Sw; optional core-calibrated regression. Standards: Timur (1968). |
| 9 | `FormationTopPicker` | K | Threshold-crossing or gradient-change detection on GR/Rt/sonic to identify formation tops; emits `FormationTop` list with depth and confidence. Standards: WITSML `FormationMarker`. |
| 10 | `CoreToLogDepthMatcher` | ST | Optimizes MD shift between core and wireline depths via cross-correlation of core porosity (or CT density) against density/neutron logs over a search range. Standards: SPWLA best practice; API RP 40. |
| 11 | `DeviationSurveyParser` | K | Parses wellbore deviation survey (CSV, LAS DLMD, or WITSML trajectoryStn); extracts MD, inclination, azimuth; validates magnetic dip correction reference. |
| 12 | `WellTrajectoryCalculator` | K | MD/Inc/Azi → 3D Cartesian (northing, easting, TVD) via minimum curvature; computes DLS per 30-m interval. Standards: ISCWSA minimum curvature; WITSML. |
| 13 | `WitsmlDrillingMonitor` | K | Parses streaming WITSML 2.0 channel set (ROP, WOB, torque, SPP, flow rate, bit depth); flags out-of-range values against operating envelopes; emits `DrillingParameters` with alarms. |
| 14 | `MudLoggingIngester` | K | Parses WITSML `mudLog` or CSV: lag-corrected gas shows (total gas, C1–C5 chromatography), lithology descriptions, ROP annotations. Standards: WITSML `mudLog`; AGIP conventions. |
| 15 | `WellCompletionIngester` | K | Parses PPDM/PRODML/JSON completion records: perforation intervals, frac stages (fluid, proppant, injection rate), tubing configs, packer depths. Standards: PRODML `wellboreCompletion`. |

### Reservoir Engineering (9)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `EclipseSmspecParser` | K | Reads ECLIPSE `.SMSPEC` + `.UNSMRY` binary files; decodes WOPR/WWPR/WGPR/WBHP/FOPT keyword vectors; returns time-series per keyword. Standards: Schlumberger ECLIPSE 100/300. |
| 2 | `CmgResultParser` | K | Reads CMG IMEX/GEM `*.irf`/`*.mrf` binary or `*.out` ASCII; extracts field and well production/injection time series and pressure maps per layer. |
| 3 | `MaterialBalanceCalculator` | K | Havlena-Odeh linear material balance for oil reservoirs; fits F vs. (Eo + m×Eg + Efw + We) to determine OOIP and gas cap size. Standards: Havlena & Odeh (1963). |
| 4 | `ArpsDeclineCurveFitter` | K | Fits exponential/hyperbolic/harmonic Arps decline via Levenberg-Marquardt; returns qi, Di, b, EUR, and 95% prediction intervals. Standards: Arps (1945); SPE-168966. |
| 5 | `ProductionAllocationEngine` | ST | Well-test loader → allocation factor calculator → commingled rate splitter → per-zone allocator. Allocates field/separator production to wells and zones using well-test ratios; handles retroactive re-allocation. Standards: PRODML; OSDU. |
| 6 | `PressureTransientAnalyzer` | ST | Pressure data cleaner → superposition builder → derivative calculator → type curve matcher → kh/skin extractor. PBU/DD analysis: log-derivative, radial flow regime, kh, skin, reservoir pressure. Standards: Lee, Rollins & Spivey (2003). |
| 7 | `PvtTableParser` | K | Parses ECLIPSE PVTO/PVTG/PVTW/PVDG/DENSITY or CMG PVT tables into structured fluid property objects; validates monotonicity and pressure coverage. |
| 8 | `ReservesEstimationPipeline` | ST | STOIIP/GIIP volumetric → DCA EUR → Monte Carlo over uncertainty ranges → 1P/2P/3P categorizer. Standards: SPE-PRMS (2018); SEC Rule 4-10(a). |
| 9 | `TypeCurveFitter` | K | Normalized rate-time type curve from analog well histories via nearest-neighbor matching; returns p10/p50/p90 envelopes. Standards: SPE-168975. |

### Production Operations (10)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `ScadaHistorianIngester` | K | Connects to OSIsoft PI / Aveva PI AF historian (or CSV export); retrieves compressed time-series tags (recorded, interpolated, or summary mode). Standards: PI-SDK/AFSDK; OPC-UA. |
| 2 | `ProductionRateNormalizer` | K | Converts raw SCADA readings (orifice DP, turbine pulse, mass flow) to stock-tank barrels and standard cubic feet using fluid properties and T/P corrections. Standards: AGA-7/9; API MPMS Ch. 12. |
| 3 | `DowntimeEventClassifier` | K | Classifies zero/near-zero rate periods by cause code using duration, rate profile shape, and SCADA alarm context; emits downtime log with deferred BOE and availability %. Standards: PRODML `deferredProduction`; IOGP Report 456. |
| 4 | `RodPumpOptimizer` | K | Analyzes rod pump dynagraph (surface or downhole card); detects fillage, gas interference, fluid pound, leaks; recommends SPM or POC setpoints. Standards: API RP 11L; Gibbs (1963). |
| 5 | `EspHealthMonitor` | K | Monitors ESP parameters (current, VFD Hz, intake/discharge pressure, flow) against manufacturer performance curves; computes efficiency and predicts time-to-failure. Standards: API RP 11S4. |
| 6 | `GasLiftOptimizer` | K | Calculates optimal gas injection rate per well under lift-gas availability constraints using IPR/TPR and gradient allocation optimization. Standards: SPE-19092; Brown (1984). |
| 7 | `SeparatorTestProcessor` | K | Processes separator test data (separator oil/water/gas rates, GOR, BS&W, shrinkage) to compute stock-tank rates and WOR; validates meter consistency. Standards: API MPMS Ch. 20.1; PRODML `wellTest`. |
| 8 | `TankGaugingProcessor` | K | Converts ullage/dip gauge readings + temperature + API gravity to net oil volumes in STB; applies VCF corrections. Standards: API MPMS Ch. 3 & 11. |
| 9 | `FlaringMeasurementProcessor` | K | Computes flared gas volumes and CO2/CH4/NOx/CO2e emissions from flare tip measurements and gas composition; flags regulatory limit exceedances. Standards: EPA AP-42; Alberta AER D060. |
| 10 | `WaterInjectionTracker` | K | Processes injector well data (rate, WHP, BHP); computes injectivity index and voidage replacement ratio; flags above-fracture-pressure operation. Standards: IOGP Report 484. |

### Facilities & Pipeline Integrity (6)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `PigRunDataProcessor` | ST | Binary decoder → distance indexer → anomaly detector → severity classifier → report builder. Processes ILI/smart pig MFL or UT data; classifies wall-thickness anomalies by ASME B31.8 depth thresholds; outputs immediate vs. scheduled repair lists. Standards: API 1163; NACE SP0102. |
| 2 | `CorrosionRateCalculator` | K | Linear regression on repeated UT thickness measurements; computes corrosion rate (mm/yr), remaining wall life, and next inspection date. Standards: API 510/570; DNV-RP-G101. |
| 3 | `PsvTestRecordParser` | K | Parses PSV calibration records; flags valves outside set-pressure tolerance and overdue for re-test. Standards: API 510; ASME PTC 25; OSHA 29 CFR 1910.119. |
| 4 | `GasChromatographyAnalyzer` | K | Parses GC analysis reports; computes mole fractions (C1–C6+, N2, CO2, H2S), Wobbe Index, HHV, relative density, and z-factor. Standards: AGA-8; GPA 2172; ISO 6976. |
| 5 | `Scope1EmissionsReporter` | ST | Flaring loader → combustion emitter → fugitive estimator → venting calculator → aggregator → category reporter. Full direct GHG inventory (combustion, fugitives, venting) in tonnes CO2e. Standards: IPCC 2019; EPA 40 CFR Part 98; ISO 14064-1; OGMP 2.0. |
| 6 | `EnergyEfficiencyKpiCalculator` | K | GHG intensity (kg CO2e/BOE), energy intensity (GJ/BOE), flaring intensity, water injection energy, and generator fuel efficiency; benchmarks against peer fields. Standards: IOGP Report 592; IPIECA guidance. |

### Geospatial / GIS (5)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `WellLocationProjector` | K | Reprojects well surface locations and 3D wellbore path vertices between CRS (NAD83 State Plane ↔ WGS84 ↔ UTM); validates coordinates against play bounding box. Standards: EPSG; OSDU Spatial Reference Service. |
| 2 | `LeaseBlockProcessor` | K | Parses federal/state/offshore lease block shapefiles; dissolves polygons by operator; computes acreage; flags HBP expiry proximity. Standards: BLM PLSS; BOEM block system. |
| 3 | `InfrastructureAssetMapper` | K | Ingests pipeline centrelines and facility points; builds network topology graph; validates connectivity; flags orphaned assets and total pipeline km. Standards: PPDM `FACILITY`; OGC WFS. |
| 4 | `FaultProximityAnalyzer` | K | Computes minimum 3D distance from each wellbore trajectory to each interpreted fault surface (triangulated mesh); flags wellbores within configurable risk radii. Standards: ISCWSA anti-collision; Petrel fault model export. |
| 5 | `BoundaryProximityChecker` | K | 2D and 3D distances from wellbores to lease/permit/regulatory boundary polygons; identifies subsurface boundary crossings at reservoir intervals. Standards: COGCC Rule 318A; ERCB Directive 056. |

### Cross-Domain SubTapestry Pipelines (4)

| # | Name | Type | What it does |
|---|------|------|--------------|
| 1 | `WellborePetrophysicsWorkflow` | ST | LAS ingestor → spike remover → depth-shift corrector → environmental corrector → Vshale → porosity → Sw → permeability → formation top picker. Full interpreted log suite from raw LAS; each inner knot independently cached for partial re-runs. |
| 2 | `SeismicToWellTieWorkflow` | ST | Well path projector → wavelet extractor → synthetic seismogram generator → correlation calculator → time-depth relationship builder. Calibrates seismic horizon picks in TWT to formation tops in depth. Standards: Sheriff & Geldart (1995). |
| 3 | `FieldProductionReportingWorkflow` | ST | SCADA ingestor → rate normalizer → downtime classifier → allocation engine → tank gauging → flaring calculator → GHG intensity KPI → report packager. Full monthly regulatory production report from raw historian data. Standards: PRODML 2.1; OSDU; Alberta AER ST-39; Texas RRC PR; BOEM OGOR. |
| 4 | `DeclineCurveReservesWorkflow` | ST | Production ingestor → rate normalizer → Arps DCA fitter → EUR aggregator → type curve benchmarker → PRMS categorizer → SEC report builder. Full reserves estimation for a portfolio of wells. Standards: SPE-PRMS (2018); SEC Rule 4-10(a); NI 51-101. |

---

## Additional Protocols for Connectors

### `pirn.domains.connectors.protocols`
- `FileFormat` — `read(path) -> AsyncIterator[Any]`, `write(path, data)` — consumed by storage connectors
- `DatabaseConnectionPool` — async connection pool lifecycle (`__aenter__`/`__aexit__`)
- `ConnectionConfig` — per-connector credential dataclass, injected from env vars or secrets manager

---

## Additional Protocols Needed (ML)

### `pirn.domains.ml.protocols`
- `LineageStore` — for `ModelLineageTracker`
- `FeatureStoreProvider` — for `FeatureStoreReader` / `FeatureStoreWriter`
- `EmbeddingProvider` — for `TextEmbeddingExtractor`
- `ImageEncoderProvider` — for `ImageEmbeddingExtractor`

---

## KnotRegistry Naming Convention

All specializations register under domain-namespaced keys:

```
data.full_refresh_extract
data.scd_type0_fixed
data.scd_type2_history_tracking
data.scd_type7_dual_surrogate
data.fuzzy_deduplicator
data.geo_enricher
connectors.postgres
connectors.bigquery
connectors.kafka
connectors.salesforce
connectors.opentelemetry
agents.react_loop
agents.corrective_rag
agents.sql_agent
ml.bayesian_opt_tuner
ml.walk_forward_validator
ml.binary_classification_pipeline
health.fhir_patient_ingestor
health.variant_caller
health.eeg_ica_decomposer
health.wsi_tile_extractor
health.survival_analysis_pipeline
signal.stft_analyzer
signal.dwt_denoiser
signal.lms_adaptive_filter
signal.kalman_filter
signal.speaker_diarization_pipeline
oilgas.segy_file_ingester
oilgas.las_file_ingester
oilgas.arps_decline_curve_fitter
oilgas.eclipse_smspec_parser
oilgas.scope1_emissions_reporter
oilgas.wellbore_petrophysics_workflow
```
