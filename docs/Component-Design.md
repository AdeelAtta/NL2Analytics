# Component Design

**Enterprise Data Intelligence Platform — Phase 2 Architecture & Design**

| Metadata | Value |
|----------|-------|
| **Author** | Founding CTO |
| **Date** | July 2026 |
| **Status** | Draft |
| **Version** | 1.0 |
| **Cross-References** | [System-Architecture.md](./System-Architecture.md), [Knowledge-Engine.md](./Knowledge-Engine.md), [Data-Flow.md](./Data-Flow.md), [API-Design.md](./API-Design.md) |

---

## 1. Component Overview

Every component is designed as a **Knowledge Engine consumer, producer, or both**. No component holds authoritative state. The Knowledge Engine is the single source of truth.

```
                    ┌──────────────────────────────────────────────┐
                    │            KNOWLEDGE ENGINE API              │
                    └──┬──────────┬──────────┬──────────┬──────────┘
                       │          │          │          │
         ┌─────────────┼──────────┼──────────┼──────────┼─────────────┐
         │             │          │          │          │             │
         ▼             ▼          ▼          ▼          ▼             ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ Schema   │ │ Context  │ │  Query   │ │ Policy   │ │Executor  │ │ Learning │
    │Intell.   │ │ Retriever│ │ Planner  │ │Enf.      │ │          │ │  Loop    │
    │(Producer)│ │(Consumer)│ │(Consumer)│ │(Consumer)│ │(C+P)     │ │ (C+P)    │
    └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
   │ Learning │ │ Feedback │ │   API    │ │    UI    │
   │  Loop    │ │ Collector│ │  Layer   │ │(Consumer)│
   │ (C+P)    │ │(Producer)│ │ (C+P)    │ └──────────┘
   └──────────┘ └──────────┘ └──────────┘
```

---

## 2. Schema Intelligence (Producer)

### 2.1 Purpose

Discover, infer, and enrich database schema knowledge. This is the **primary knowledge ingestion path** — without Schema Intelligence, the Knowledge Engine is empty.

### 2.2 Knowledge Engine Contract

| Operation | Direction | Description |
|-----------|-----------|-------------|
| `ingest("ddl_introspection", data)` | Write | Store raw schema metadata |
| `refresh("descriptions", database_id)` | Write | Trigger LLM-based description generation |
| `refresh("embeddings", database_id)` | Write | Rebuild vector index for schema elements (vector index removed) |
| `refresh("relationships", database_id)` | Write | Run relationship inference |
| `query("schema", filters)` | Read | Check existing schema state |

### 2.3 Pipeline

```
Database ──► Connector ──► DDL Parser ──► Diff Engine ──► Schema Store
                                                  │
                                        ┌─────────┴─────────┐
                                        ▼                   ▼
                                 Name Annotator      Relationship Inferer
                                        │                   │
                                        └─────────┬─────────┘
                                                    ▼
                                             Embedder ──► Vector Index [REMOVED]
                                                                       
                                            Graph Builder ──► Knowledge Graph
```

### 2.4 Sub-Components

#### Connector

| Property | Value |
|----------|-------|
| **Technology** | SQLAlchemy with per-dialect drivers |
| **Interface** | `introspect(database_id) → Schemas` |
| **Output** | List of schemas, tables, columns, types, constraints, indexes, sample values |
| **Error handling** | Timeout per query (30s), retry (3x), partial results on failure |
| **Caching** | Full introspection cached 24h; incremental checksum-based |

Extracts:
- Table/column names, data types, nullable, defaults, primary keys
- Explicit foreign key constraints
- Index definitions
- Approximate row counts (ANALYZE or `information_schema`)
- Sample values (first 5 non-null rows per column)

#### DDL Parser

| Property | Value |
|----------|-------|
| **Technology** | Custom parser using SQLAlchemy reflection |
| **Output** | Structured schema objects (Database, Table, Column, Relationship) |
| **Normalization** | Canonical type names across dialects (e.g., `VARCHAR(255)` normalized) |

#### Diff Engine

| Property | Value |
|----------|-------|
| **Function** | Compare current introspection vs last known state |
| **Output** | Added/modified/removed tables, columns, relationships |
| **Trigger** | Full refresh on new tables; incremental for column changes |

#### Name Annotator

| Property | Value |
|----------|-------|
| **Technology** | LLM (SQLCoder-7b for simple, Qwen2.5-72B for complex schemas) |
| **Prompt** | System prompt with: table name, column names, types, sample values, known business context |
| **Input** | Table + columns + sample values |
| **Output** | `description` (business meaning), `business_name` (human-readable name), `is_pii` flag, `tags` |
| **Confidence** | Self-reported 0.0-1.0; sampled for human validation |
| **Batch size** | 10 tables per LLM call; parallel batch processing |
| **Cost** | ~$0.002 per table (Qwen2.5-72B self-hosted) |

#### Relationship Inferer

| Property | Value |
|----------|-------|
| **Strategies** | 1. Explicit FK constraints (100% confidence), 2. Naming pattern match (`orders.customer_id` → `customers.id`), 3. Query history mining (frequent JOIN patterns), 4. LLM inference (fallback) |
| **Output** | Relationship objects with confidence score + detection method |
| **Minimum confidence** | 0.5 for automated inference; 0.3 below stored as "suggested" |

#### Embedder

| Property | Value |
|----------|-------|
| **Model** | BGE-M3 (1024-dim, multilingual) |
| **Input** | `column_name + " " + table_name + " " + description` |
| **Output** | Float vector [1024] |
| **Batch size** | 100 texts per batch |
| **Storage** | Upsert to Qdrant `column_embeddings` collection (Qdrant removed) |

#### Graph Builder

| Property | Value |
|----------|-------|
| **Function** | Link business terms to schema elements in knowledge graph |
| **Input** | Business term definitions + column names + descriptions |
| **Strategy** | LLM-based term-to-column mapping; confidence scoring |
| **Output** | `term_column_mappings` entries |

### 2.5 Error States

| State | Behavior |
|-------|----------|
| Database unreachable | Retry queue; alert admin. Existing schema knowledge remains available. |
| LLM enrichment fails | Partial schema without descriptions. Retry on next refresh cycle. |
| Embedding generation fails | Vector search degrades to keyword-only. Retry on next refresh. |

### 2.6 Performance Budget

| Operation | Target |
|-----------|--------|
| Introspect 100-table DB | <30s |
| Generate descriptions for 100 tables | <120s (parallel LLM) |
| Generate embeddings for 100 columns | <10s |
| Relationship inference for 100 tables | <30s |
| **Full pipeline (100 tables)** | **<3 min** |

---

## 3. Context Retriever (Consumer)

### 3.1 Purpose

Given a natural language query, retrieve the most relevant schema context from the Knowledge Engine. This is the **primary query-time knowledge consumption path**.

### 3.2 Knowledge Engine Contract

| Operation | Direction | Description |
|-----------|-----------|-------------|
| `retrieve(query, filters)` | Read | Semantic search over schema + QA pairs + docs |
| `query("schema", filters)` | Read | Structured lookup (e.g., column details) |
| `query("query_history", filters)` | Read | Find similar past queries |

### 3.3 Pipeline

```
NL Query ──► Query Analyzer ──► Query Rewriter ──► Hybrid Retriever ──► Ranker ──► Context
                                   │                      │
                              Knowledge Engine        Knowledge Engine
                              (history patterns)      (vector + schema)
```

### 3.4 Sub-Components

#### Query Analyzer

| Property | Value |
|----------|-------|
| **Function** | Extract entities, intent, time constraints, filters, aggregation hints |
| **Technology** | LLM (SQLCoder-7b) with structured output |
| **Output** | `{entities: ["revenue", "region"], intent: "aggregation", time_range: "Q2 2026", filters: {...}}` |
| **Latency** | <500ms |

#### Hybrid Retriever

| Property | Value |
|----------|-------|
| **Strategies** | 1. **Vector search** (Qdrant — removed): semantic similarity to column embeddings, QA pair embeddings, doc embeddings. 2. **Keyword search** (PostgreSQL full-text): `tsvector` on column names + descriptions. 3. **Query history match**: find similar previous queries and their successful SQL. |
| **Top-K per strategy** | Vector: 20, Keyword: 10, History: 5 |
| **Fusion** | Reciprocal Rank Fusion (RRF) across strategy results |
| **Filters applied** | Tenant ID, database scope, data type, PII flag, confidence threshold |

#### Ranker

| Property | Value |
|----------|-------|
| **Scoring factors** | Embedding similarity (0.4), Column name match (0.2), Description match (0.2), Query history frequency (0.1), Recency (0.1) |
| **Output** | Top-K ranked context entries with combined score |
| **Top-K** | 15 (configurable per tenant) |

### 3.5 Context Output

```jsonc
{
  "relevant_tables": [
    {"table_id": "uuid", "table_name": "revenue", "description": "Daily revenue records", "score": 0.91}
  ],
  "relevant_columns": [
    {"column_id": "uuid", "column_name": "amount", "table_name": "revenue", "description": "Net revenue in USD", "data_type": "numeric", "score": 0.89}
  ],
  "relevant_relationships": [
    {"source": "revenue.region_id", "target": "regions.id", "confidence": 0.95}
  ],
  "similar_queries": [
    {"question": "show me revenue by region", "sql": "SELECT r.name, SUM(rev.amount)...", "accuracy": 0.95}
  ],
  "latency_ms": 85
}
```

---

## 4. Query Planner (Consumer)

### 4.1 Purpose

Given a natural language query and retrieved context, produce a query execution plan. Determines what to query, how to join, which metrics to compute.

### 4.2 Knowledge Engine Contract

| Operation | Direction | Description |
|-----------|-----------|-------------|
| `resolve(term, context)` | Read | Map business terms to physical columns |
| `query("schema", filters)` | Read | Lookup table structures, relationships |
| `query("metric_definitions", filters)` | Read | Find metric formulas |

### 4.3 Pipeline

```
NL Query + Context ──► Intent Classifier ──► Query Decomposer ──► Join Path Finder
                                                                       │
                                                                       ▼
                                                                Metric Resolver
                                                                       │
                                                                       ▼
                                                                 Plan
```

### 4.4 Sub-Components

#### Intent Classifier

| Property | Value |
|----------|-------|
| **Classes** | simple_select, aggregation (GROUP BY), time_series, multi_join, cross_database, metric_query, comparison, trend, exploratory |
| **Technology** | Lightweight classifier (logistic regression or small LLM) |
| **Output** | Intent class + confidence |
| **Latency** | <100ms |

#### Query Decomposer

| Property | Value |
|----------|-------|
| **Trigger** | Complex intents (multi_join, cross_database, comparison) |
| **Function** | Break into sub-queries with temporal ordering |
| **Output** | List of sub-query plans with dependencies |
| **Example** | "Compare revenue by region for Q1 vs Q2 2026" → Sub-query 1: revenue by region Q1 2026, Sub-query 2: revenue by region Q2 2026, Merge: side-by-side comparison |

#### Join Path Finder

| Property | Value |
|----------|-------|
| **Input** | Selected tables + columns from context |
| **Strategy** | 1. Lookup explicit relationships in schema store. 2. Lookup inferred relationships. 3. Build shortest path through knowledge graph. 4. LLM fallback for unknown paths. |
| **Output** | Join tree: which tables to join, on which columns, join type |
| **Confidence** | Per-join confidence score |

#### Metric Resolver

| Property | Value |
|----------|-------|
| **Input** | Business term references in query (e.g., "MRR", "churn rate") |
| **Function** | Lookup metric definition in metric store. Map to physical SQL. |
| **Output** | SQL snippet for metric computation + dimension availability |

### 4.5 Plan Output

```jsonc
{
  "plan_id": "uuid",
  "query_type": "aggregation",
  "sub_queries": [
    {
      "id": 1,
      "databases": ["uuid"],
      "tables": ["revenue", "regions"],
      "join_path": [
        {"left": "revenue.region_id", "right": "regions.id", "type": "inner", "confidence": 0.95}
      ],
      "aggregation": {"function": "SUM", "column": "revenue.amount", "alias": "total_revenue"},
      "group_by": ["regions.name"],
      "filters": {"revenue.date": {"gte": "2026-01-01", "lte": "2026-06-30"}}
    }
  ],
  "cross_database": false
}
```

---

## 5. NL2SQL Generator (Consumer)

### 5.1 Purpose

Generate SQL from natural language using retrieved context and query plan. This is the **most visible consumer** of the Knowledge Engine, but architecturally it is just one of many consumers.

### 5.2 Knowledge Engine Contract

| Operation | Direction | Description |
|-----------|-----------|-------------|
| `retrieve(query, filters)` | Read | Get context (via Context Retriever, not directly) |
| `query("qa_pairs", filters)` | Read | Find similar Q&A examples |

### 5.3 Pipeline

```
Context + Plan ──► Schema Linker ──► Prompt Builder ──► Candidate Generator ──► Selector ──► Reflection Loop
                                                            │                           │
                                                       Model Router                  Knowledge Engine
                                                            │                      (store final SQL)
                                                  ┌────────┼────────┐
                                                  ▼        ▼        ▼
                                             SQLCoder  Qwen2.5  DeepSeek
                                              7b       72B       V3
```

### 5.4 Sub-Components

#### Schema Linker

| Property | Value |
|----------|-------|
| **Function** | Map NL terms to specific schema elements using context + planner output |
| **Input** | Raw NL query, context entries, plan |
| **Output** | `{linked_terms: {"revenue": {"table": "revenue", "column": "amount"}, "region": {"table": "regions", "column": "name"}}}` |

#### Prompt Builder

| Property | Value |
|----------|-------|
| **Template** | System: role + rules + output format. Context: relevant schema + examples. User: NL query + plan. |
| **Context window** | Dynamic: fits within model's context limit. Prioritize: schema (60%), examples (20%), instructions (20%). |
| **Optimization** | Truncate column lists to top 10 relevant columns per table. Use `business_name` when available. |

#### Candidate Generator

| Property | Value |
|----------|-------|
| **Candidates** | 3 SQL candidates |
| **Model Router** | Routes to: SQLCoder-7b (simple), Qwen2.5-72B (medium), DeepSeek-V3 (complex). Router = intent classifier + token count heuristic. |
| **Temperature** | 0.1 for deterministic, 0.3 for exploration |
| **Output** | 3 SQL strings + model used + latency |

#### Selector

| Property | Value |
|----------|-------|
| **Scoring** | 1. Compilation check (syntax error?). 2. Schema validity (tables/columns exist?). 3. Cost estimate (token count + estimated execution). 4. Confidence score from model. |
| **Output** | Best candidate + score + alternatives for user to compare |
| **Fallback** | If all 3 fail, retry with more permissive settings or escalate to cloud model |

#### Reflection Loop

| Property | Value |
|----------|-------|
| **Trigger** | Candidate produces no results, syntax error, or low confidence |
| **Action** | Feed error message + SQL back to model with instruction to fix |
| **Max iterations** | 2 (cost control) |
| **Output** | Corrected SQL or error explanation |

### 5.5 Model Routing

| Tier | Model | Query Types | Cost/Query | Latency |
|------|-------|-------------|------------|---------|
| **Simple** | SQLCoder-7b-2 | 1-2 table SELECT, simple WHERE, basic GROUP BY | ~$0.0003 | <1s |
| **Medium** | Qwen2.5-72B | 3-5 table joins, subqueries, window functions | ~$0.002 | <3s |
| **Complex** | DeepSeek-V3 | Multi-join, CTEs, complex aggregations, cross-DB | ~$0.01 | <5s |
| **Fallback** | GPT-4o / Claude | Edge cases, reflection repair, out-of-distribution | ~$0.02 | <5s |

**Routing rules**:
- Simple: token count < 50 AND table references < 3 AND no subqueries/CTEs
- Medium: token count 50-200 OR table references 3-5 OR simple subquery
- Complex: token count > 200 OR table references > 5 OR CTEs OR cross-DB
- Fallback: reflection iteration OR any tier fails

---

## 6. Guardrail Stack (Consumer + Producer)

### 6.1 Purpose

Ensure every query is safe, authorized, and auditable. This is both a **consumer** (reads RBAC policies, schema scope) and **producer** (writes audit events).

### 6.2 Knowledge Engine Contract

| Operation | Direction | Description |
|-----------|-----------|-------------|
| `query("rbac_policies", filters)` | Read | Get user's role and permissions |
| `query("schema", filters)` | Read | Check table/column existence and PII flags |
| `store("audit_log", data)` | Write | Log every policy enforcement decision |

### 6.3 Layer Architecture (Fail-Closed)

```
SQL ──► L1: Intent Classification ──► BLOCK (not a data query)
             │ PASS
             ▼
         L2: SQL Sanitization ──► BLOCK (injection detected)
             │ PASS
             ▼
        L3: RBAC Schema Scoping ──► BLOCK (unauthorized access)
             │ PASS
             ▼
        L4: Query Cost Ceiling ──► BLOCK (exceeds cost/time)
             │ PASS
             ▼
        L5: SQL Validation ──► BLOCK (syntax error)
             │ PASS
             ▼
        L6: Read-Only Enforcement ──► BLOCK (DDL/DML detected)
             │ PASS
             ▼
         L7: Audit Logging ──► PASS
              │
              ▼
         L8: Data Classification ──► BLOCK (PII exfiltration attempt)
              │ PASS
              ▼
         L9: Advanced Validation ──► BLOCK (denylisted function)
              │ PASS
              ▼
         L10: Anomaly Detection ──► BLOCK (unusual query pattern)
              │ PASS
              ▼
              EXECUTE (all 10 layers passed)
```

### 6.4 Layer Details

#### L1: Intent Classification

| Property | Value |
|----------|-------|
| **Check** | Is this a legitimate data query request? |
| **Blocks** | Non-query text (conversation, commands, gibberish), attempts to bypass system prompt, requests for system-level actions |
| **Technology** | Lightweight classifier (Regex + LLM) |
| **Latency** | <50ms |
| **False positive rate target** | <1% |
| **False negative rate target** | <0.1% |

#### L2: SQL Sanitization

| Property | Value |
|----------|-------|
| **Check** | Does the input contain SQL injection, prompt injection, or special characters? |
| **Blocks** | SQL keywords in NL input (`DROP`, `DELETE`, `ALTER`), encoded injection attempts, excessive special characters |
| **Technology** | Regex + allowlist + LLM-based prompt injection detection |
| **Latency** | <20ms |

#### L3: RBAC Schema Scoping

| Property | Value |
|----------|-------|
| **Check** | Does the user have permission to access the tables/columns referenced? |
| **Blocks** | Query referencing tables user doesn't have access to, query referencing PII columns the user's role masks |
| **Technology** | Knowledge Engine RBAC lookup + SQL parser to extract table references |
| **Latency** | <30ms |

#### L4: Query Cost Ceiling

| Property | Value |
|----------|-------|
| **Check** | Will this query exceed cost or time limits? |
| **Blocks** | Queries estimated to scan too many rows, queries with no WHERE clause on large tables, cross-join cartesian products |
| **Technology** | Token count estimate + table size estimate + heuristic rules |
| **Latency** | <10ms |

#### L5: SQL Validation

| Property | Value |
|----------|-------|
| **Check** | Is the SQL syntactically correct? |
| **Blocks** | Syntax errors, references to non-existent tables/columns, type mismatches |
| **Technology** | SQL parser (sqlglot) with schema awareness |
| **Latency** | <20ms |

#### L6: Read-Only Enforcement

| Property | Value |
|----------|-------|
| **Check** | Does the SQL attempt to modify data? |
| **Blocks** | INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT, REVOKE |
| **Technology** | SQL parser statement type detection |
| **Latency** | <5ms |

#### L7: Audit Logging

| Property | Value |
|----------|-------|
| **Check** | Log everything |
| **Action** | Write audit event to Knowledge Engine audit store. Include: user, query, SQL generated, policy enforcement decisions (pass/fail per layer), timestamp, trace ID. |
| **Technology** | Async write to PostgreSQL audit store |
| **Latency** | <5ms (async, non-blocking) |

#### L8: Data Classification

| Property | Value |
|----------|-------|
| **Check** | Does the query access sensitive data (PII, financial, credentials) unauthorized for this role? |
| **Blocks** | Query referencing PII columns when role lacks clearance, query attempting cross-tenant data access, query exfiltrating bulk sensitive data |
| **Technology** | Column PII tags from schema store + role-based clearance matrix + row count threshold |
| **Latency** | <20ms |

#### L9: Advanced Validation

| Property | Value |
|----------|-------|
| **Check** | Does the SQL violate allowlist/denylist rules, use dangerous functions, or exceed resource quotas? |
| **Blocks** | Denylisted functions (`COPY`, `pg_sleep`, `lo_export`), queries exceeding per-tenant row/time quotas, SQL matching blocked patterns |
| **Technology** | sqlglot AST traversal + per-tenant allowlist/denylist + quota counters from KE config store |
| **Latency** | <15ms |

#### L10: Anomaly Detection

| Property | Value |
|----------|-------|
| **Check** | Does this query deviate from the tenant's historical query baseline? |
| **Blocks** | Query with unusual structure (first time seeing this table join pattern), query with anomalous row count estimate (>2σ from baseline), query at unusual time of day |
| **Technology** | Per-tenant query baseline (rolling 7-day window) stored in KE metric store + statistical comparison |
| **Latency** | <30ms |

### 6.5 Policy Enforcement Response

```jsonc
// Failed policy layer
{
  "allowed": false,
  "blocked_by": "L3: RBAC Schema Scoping",
  "reason": "User role 'business_analyst' does not have access to table 'hr.employee_salaries'",
  "user_message": "This query would access salary data, which your role doesn't have permission to view. Please rephrase or contact your data team."
}

// All policy layers passed
{
  "allowed": true,
  "checks": {
    "intent": {"passed": true},
    "sanitization": {"passed": true},
    "rbac": {"passed": true, "tables_accessed": 3, "pii_columns_masked": 1},
    "cost": {"passed": true, "estimated_rows": 15000, "limit": 1000000},
    "validation": {"passed": true},
    "readonly": {"passed": true}
  },
  "execution_id": "uuid"
}
```

---

## 7. Executor (Consumer + Producer)

### 7.1 Purpose

Execute the guarded SQL against the target database and return results. Writes query results and metadata back to the Knowledge Engine.

### 7.2 Knowledge Engine Contract

| Operation | Direction | Description |
|-----------|-----------|-------------|
| `query("configuration", filters)` | Read | Get database connection config |
| `store("query_log", data)` | Write | Log query + result + metadata |
| `store("audit_log", data)` | Write | Log execution event |

### 7.3 Pipeline

```
SQL + Execution ID ──► Connection Pool ──► Query Runner ──► Result Formatter ──► Response
                                                │
                                                ▼
                                          Knowledge Engine
                                        (history + audit)
```

### 7.4 Sub-Components

#### Connection Pool

| Property | Value |
|----------|-------|
| **Technology** | SQLAlchemy connection pool per database |
| **Pool size** | 5-20 connections per database (configurable) |
| **Timeout** | 30s connection timeout, 60s query timeout |
| **Encryption** | TLS for all database connections |

#### Query Runner

| Property | Value |
|----------|-------|
| **Execution** | Async SQL execution via asyncpg/psycopg async |
| **Cancellation** | Support `pg_cancel_backend` for long-running queries |
| **Error handling** | Syntax errors → return to NL2SQL for repair. Execution errors → user-friendly message. |

#### Result Formatter

| Property | Value |
|----------|-------|
| **Output formats** | JSON (default), CSV, Arrow (for large results) |
| **Pagination** | Server-side pagination for >1000 rows |
| **Truncation** | Max rows: 10,000 (configurable per tenant) |
| **Performance** | Streaming response for large datasets |

---

## 8. Learning Loop (Consumer + Producer)

### 8.1 Purpose

Read feedback from Knowledge Engine, transform into improved knowledge, write back. This is the **primary self-improvement path**.

### 8.2 Knowledge Engine Contract

| Operation | Direction | Description |
|-----------|-----------|-------------|
| `query("feedback", filters)` | Read | Get pending unprocessed feedback |
| `query("query_logs", filters)` | Read | Get query patterns |
| `store("qa_pair_embeddings", data)` | Write | Add validated Q&A pairs |
| `refresh("embeddings", scope)` | Write | Rebuild vector index |
| `refresh("descriptions", scope)` | Write | Regenerate schema descriptions |
| `ingest("prompt_update", data)` | Write | Update prompt templates |
| `ingest("knowledge_graph", data)` | Write | Update business term mappings |

### 8.3 Pipeline

```
Feedback ──► Collector ──► Validator ──► Q&A Builder ──► Vector Index
                                                │
                                        ┌───────┴───────┐
                                        ▼               ▼
                                   Schema Enricher  Prompt Optimizer
                                        │               │
                                        ▼               ▼
                                   Schema Store    Config Store
                                   (descriptions)  (prompts)
```

### 8.4 Sub-Components

#### Feedback Collector

| Property | Value |
|----------|-------|
| **Input** | Feedback events from Knowledge Engine feedback store |
| **Cadence** | Batch process every 5 minutes |
| **Output** | Batch of validated feedback items |

#### Feedback Validator

| Property | Value |
|----------|-------|
| **Checks** | 1. Is correction valid SQL? 2. Does it return non-empty results? 3. Is it meaningfully different from original? 4. Is user reliable (not spam)? |
| **Pass rate** | ~60-80% of corrections pass validation |
| **Rejected** | Stored but not used for learning; flagged for human review if pattern of rejection |

#### Q&A Builder

| Property | Value |
|----------|-------|
| **Input** | Validated corrections (NL query + corrected SQL) |
| **Output** | Q&A pair embedded into vector index |
| **Metadata** | tenant_id, database_type, query_pattern, user_rating, success_rate |
| **Limit** | Max 1000 Q&A pairs per tenant before deduplication/archival |

#### Schema Enricher

| Property | Value |
|----------|-------|
| **Input** | Corrections that reveal new schema understanding (e.g., user consistently corrects column mapping) |
| **Action** | Update column descriptions, business names, or relationship confidence scores |
| **Trigger** | Same correction from 3+ different users, or same user correct same pattern 5+ times |
| **Output** | Updated schema store entries with new confidence scores |

#### Prompt Optimizer

| Property | Value |
|----------|-------|
| **Input** | Successful query patterns + corrections |
| **Action** | Add successful examples to few-shot prompt templates |
| **Strategy** | Maintain pool of top 20 most-validated Q&A pairs per tenant as dynamic few-shot examples |
| **Output** | Updated prompt configuration in Knowledge Engine Config Store |

#### Pattern Miner

| Property | Value |
|----------|-------|
| **Input** | Query history store |
| **Action** | 1. Discover most common query patterns (template extraction). 2. Find popular join paths not in schema. 3. Identify frequently co-accessed tables. |
| **Output** | Pattern records → Knowledge Graph entries for implicit relationships |
| **Cadence** | Nightly batch job |

---

## 9. Feedback Collector (Producer)

### 9.1 Purpose

Capture user feedback signals and write to Knowledge Engine.

### 9.2 Knowledge Engine Contract

| Operation | Direction | Description |
|-----------|-----------|-------------|
| `store("feedback", data)` | Write | Store feedback event |

### 9.3 Feedback Types

| Type | UI Element | Data | Priority |
|------|------------|------|----------|
| **Correction** | User edits SQL in editor | Original SQL, corrected SQL, NL query | High |
| **Approval** | "This looks right" button | Query ID, approval flag | Medium |
| **Rating** | Thumbs up/down on result | Query ID, rating | Medium |
| **Comment** | "Not what I meant" text | Query ID, free text | Low |

### 9.4 Feedback UX Principles

- Feedback must take <2 seconds to submit
- No mandatory feedback (avoid annoyance)
- "Show me why this is wrong" reveals SQL for correction
- Batch feedback requests: "How were the last 5 results?" (end of session)

---

## 10. API Layer (Consumer + Producer)

### 10.1 Purpose

Expose platform capabilities to external clients. Translates external API requests into Knowledge Engine operations.

### 10.2 Knowledge Engine Contract

| Operation | Direction | Description |
|-----------|-----------|-------------|
| All KE operations | Read/Write | Proxy external requests to Knowledge Engine |

### 10.3 API Categories

| Category | Endpoints | Knowledge Engine Mapping |
|----------|-----------|--------------------------|
| **Query** | `POST /v1/query` | Intent → Retriever → Planner → Generator → [Validator → Repair]² → Policy Enforcement → Execution → Reflection |
| **Query** | `POST /v1/query/stream` | Same, but response streamed |
| **Query** | `POST /v1/query/explain` | Return SQL + reasoning without executing |
| **Schema** | `GET /v1/databases` | `query("databases", ...)` |
| **Schema** | `GET /v1/databases/{id}/tables` | `query("tables", ...)` |
| **Schema** | `GET /v1/databases/{id}/tables/{id}/columns` | `query("columns", ...)` |
| **Knowledge** | `POST /v1/knowledge/resolve` | `resolve(term, context)` |
| **Knowledge** | `POST /v1/knowledge/search` | `retrieve(query, filters)` |
| **History** | `GET /v1/query/history` | `query("query_logs", filters)` |
| **Feedback** | `POST /v1/feedback` | `store("feedback", data)` |
| **Admin** | `GET/POST/PUT /v1/admin/*` | Various KE operations |

**Detailed API specification**: [API-Design.md](./API-Design.md)

---

## 11. UI (Consumer)

### 11.1 Purpose

Human interface to the platform. Consumes the API Layer, which consumes the Knowledge Engine.

### 11.2 Knowledge Engine Contract

| Operation | Direction | Description |
|-----------|-----------|-------------|
| All API Layer operations | Read/Write | Indirect KE access through API layer |

### 11.3 Screen Map

| Screen | Knowledge Engine Interaction |
|--------|------------------------------|
| **Chat** | `POST /v1/query` → agents: intent → retrieve → plan → generate → validate → enforce → execute → reflect; KE: retrieve → resolve → store |
| **Query History** | `GET /v1/query/history` → KE: query("query_logs") |
| **Schema Browser** | `GET /v1/databases/{id}/tables` → KE: query("schema") |
| **Knowledge Graph** | `GET /v1/knowledge/resolve?term=...` → KE: resolve |
| **Analytics** | `GET /v1/admin/metrics` → KE: query("metrics") |
| **Settings** | `PUT /v1/admin/settings` → KE: store("configuration") |

---

## 12. Component Dependencies

```
                   ┌──────────┐
                   │    UI    │
                   └────┬─────┘
                        │ HTTPS
                   ┌────▼─────┐
                   │ API Layer│
                   └────┬─────┘
                        │ HTTP/gRPC
              ┌─────────┼─────────┐
              │         │         │
        ┌─────▼────┐ ┌──▼───┐ ┌──▼──────────┐
        │ Query    │ │Guard │ │ Schema       │
        │ Pipeline │ │Stack │ │ Intelligence │
        │ (C+R+P   │ └──┬───┘ └──────────────┘
        │  +NL2SQL │    │
        │  +Exec)  │    │
        └────┬─────┘    │
             │          │
             └────┬─────┘
                  │
          ┌───────▼────────┐
          │ Knowledge Engine│
          │ API (gRPC)     │
          └───────┬────────┘
                  │
          ┌───────┴────────┐
          │ Stores (PG) — Qdrant removed │
          └────────────────┘
```

---

## 13. References

| Source | Relevance |
|--------|-----------|
| [System-Architecture.md](./System-Architecture.md) | Component roles in overall architecture |
| [Knowledge-Engine.md](./Knowledge-Engine.md) | Data models and API each component uses |
| [Data-Flow.md](./Data-Flow.md) | End-to-end flows for each component |
| [API-Design.md](./API-Design.md) | Public API surface for external consumers |
| [Phase1-Executive-Review.md](../Product-Business/Phase1-Executive-Review.md) | Feature priorities that drive component scope |
