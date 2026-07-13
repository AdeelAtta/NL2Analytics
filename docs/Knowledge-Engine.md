# Enterprise Knowledge Engine

**Enterprise Data Intelligence Platform — Phase 2 Architecture & Design**

| Metadata | Value |
|----------|-------|
| **Author** | Founding CTO |
| **Date** | July 2026 |
| **Status** | Draft |
| **Version** | 1.0 |
| **Cross-References** | [System-Architecture.md](./System-Architecture.md), [Component-Design.md](./Component-Design.md), [Data-Flow.md](./Data-Flow.md), [API-Design.md](./API-Design.md) |

> **Note:** Redis and Qdrant were removed during cleanup — the stack uses PostgreSQL only. All references below to Qdrant (Vector Index, embeddings) and Redis (cache) are historical design records; the current implementation has removed these dependencies.

---

## 1. Overview

The Enterprise Knowledge Engine (EKE) is the single source of truth for all enterprise data intelligence. It is not a database — it is a **layered knowledge system** that stores, indexes, enriches, and serves all knowledge types required for the platform.

### 1.1 What the Knowledge Engine Knows

| Knowledge Type | Example | Source | Consumer |
|----------------|---------|--------|----------|
| **Schema** | Table `orders` has columns `id`, `customer_id`, `amount`, `created_at` | Database introspection | Context Retriever, Planner, Guardrails |
| **Business Meaning** | Column `c1` in table `TBL_FCT` means "net revenue after discount" | LLM inference, human validation | Query Planner, NL2SQL Generator |
| **Relationships** | `orders.customer_id` → `customers.id` (foreign key, 95% confidence) | Relationship inference | Join Path Finder |
| **Business Terms** | "MRR" = `SELECT SUM(amount) FROM subscriptions WHERE status = 'active'` | Documentation, query mining | Metric Resolver |
| **Query History** | User asked "revenue by month" → generated SQL with timestamp | Query execution | Learning Loop, Pattern Miner |
| **Q&A Pairs** | Question: "show me top 10 customers" → SQL: `SELECT ... ORDER BY ... LIMIT 10` | Feedback validation | Context Retriever, NL2SQL |
| **Feedback** | User corrected table alias from `o` to `orders` | UI correction | Learning Loop |
| **RBAC Policies** | "Analyst role can read `orders.*` but not `users.pii`" | Admin configuration | Guardrail Stack |
| **Metrics** | "Monthly Recurring Revenue" = formula, owner, refresh cadence | Admin, automated discovery | Query Planner, Dashboard |
| **Audit** | User `alice@co.com` queried `orders` at 2026-07-10T14:30:00Z | Guardrail stack | Compliance, Debugging |

### 1.2 Architecture

```
                         ┌──────────────────────────────────┐
                         │       KNOWLEDGE ENGINE API       │
                         │  (FastAPI Service, port 8200)    │
                         │  resolve / retrieve / ingest     │
                         │  store / query / refresh         │
                         └──────────┬───────────────────────┘
                                    │
               ┌────────────────────┼────────────────────┐
               │                    │                    │
               ▼                    ▼                    ▼
    ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
    │  Knowledge Store  │  │   Vector Index   │  │   Knowledge      │
    │  (PostgreSQL)     │  │   (removed)      │  │   Pipeline       │
    │                   │  │                  │  │   (Background)   │
    │  • Schema Store   │  │  (Qdrant was     │  │                   │
    │  • Query History  │  │   removed —      │  │  • Ingestion     │
    │  • Feedback       │  │   PostgreSQL     │  │  • Enrichment    │
    │  • Audit          │  │   only)          │  │  • Validation    │
    │  • Configuration  │  │                  │  │  • Refresh       │
    │  • Metrics        │  └──────────────────┘  └──────────────────┘
    │  • Knowledge Graph│
    └──────────────────┘
```

---

## 2. Data Model

### 2.1 Naming Conventions

| Convention | Rule | Example |
|-----------|------|---------|
| **Tenant isolation** | All tables have `tenant_id` column. | `tenant_id UUID NOT NULL` |
| **Soft delete** | No destructive operations. `deleted_at TIMESTAMP` for deactivation. | `WHERE deleted_at IS NULL` |
| **Audit fields** | Every row has `created_at`, `updated_at`. | `DEFAULT NOW()` |
| **IDs** | UUID v7 (time-ordered) for all primary keys. | `id UUID PRIMARY KEY DEFAULT gen_random_uuid()` |
| **Immutable stores** | Audit and query history are append-only. No updates. | `INSERT ONLY` |

### 2.2 Schema Store (PostgreSQL)

#### `databases`
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | |
| `tenant_id` | UUID | Tenant owner |
| `name` | VARCHAR(255) | Human-readable name |
| `db_type` | VARCHAR(50) | postgresql, mysql, snowflake, bigquery, duckdb |
| `connection_config_encrypted` | TEXT | Encrypted connection string |
| `status` | ENUM | connected, disconnected, error |
| `last_introspected_at` | TIMESTAMPTZ | Last successful schema scan |
| `table_count` | INTEGER | Cached for quick reference |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |
| `deleted_at` | TIMESTAMPTZ | |

#### `tables`
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | |
| `database_id` | UUID FK → databases | Parent database |
| `schema_name` | VARCHAR(255) | Database schema (e.g., `public`) |
| `table_name` | VARCHAR(255) | Physical table name |
| `description` | TEXT | LLM-generated business description |
| `description_confidence` | FLOAT | 0.0-1.0 confidence score |
| `row_count_estimate` | BIGINT | Approximate row count |
| `is_view` | BOOLEAN | Whether this is a view |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

#### `columns`
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | |
| `table_id` | UUID FK → tables | Parent table |
| `column_name` | VARCHAR(255) | Physical column name |
| `ordinal_position` | INTEGER | Column order |
| `data_type` | VARCHAR(100) | PostgreSQL type name |
| `is_nullable` | BOOLEAN | |
| `is_primary_key` | BOOLEAN | |
| `default_value` | TEXT | |
| `description` | TEXT | LLM-generated business description |
| `description_confidence` | FLOAT | |
| `business_name` | VARCHAR(255) | Preferred business name |
| `is_pii` | BOOLEAN | Flagged as PII |
| `tags` | JSONB | Arbitrary tags array |
| `sample_values` | JSONB | Array of sample values (nullable) |
| `distinct_count` | INTEGER | Approximate distinct values |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

#### `relationships`
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | |
| `source_column_id` | UUID FK → columns | |
| `target_column_id` | UUID FK → columns | |
| `relationship_type` | ENUM | foreign_key, inferred_fk, same_as, parent_child |
| `confidence` | FLOAT | 0.0-1.0 confidence score |
| `detection_method` | ENUM | ddl_constraint, naming_pattern, query_mining, llm_inference |
| `detected_at` | TIMESTAMPTZ | |
| `created_at` | TIMESTAMPTZ | |

### 2.3 Knowledge Graph (PostgreSQL + Recursive CTEs)

#### `business_terms`
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | |
| `tenant_id` | UUID | |
| `term` | VARCHAR(255) | Business term (e.g., "Monthly Recurring Revenue") |
| `aliases` | JSONB | Alternative names (["MRR", "monthly revenue", "subscription revenue"]) |
| `definition` | TEXT | Business definition |
| `metric_formula` | TEXT | SQL formula or description |
| `category` | VARCHAR(100) | revenue, customer, product, operational |
| `owner` | VARCHAR(255) | Business owner email |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

#### `term_column_mappings`
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | |
| `business_term_id` | UUID FK → business_terms | |
| `column_id` | UUID FK → columns | Physical column this term maps to |
| `mapping_type` | ENUM | direct, computed (formula needed), approximate |
| `confidence` | FLOAT | |
| `detection_method` | ENUM | manual, llm_inferred, query_mined, doc_parsed |
| `context_condition` | TEXT | Optional: term resolves differently per context (e.g., "North Europe" = specific countries) |
| `created_at` | TIMESTAMPTZ | |

### 2.4 Vector Index (removed)

**Qdrant vector index was removed during cleanup.** The platform now relies on PostgreSQL-only storage. Previously planned collections were:

- `column_embeddings` — BGE-M3 embeddings of column names + descriptions
- `business_term_embeddings` — Term → column mappings
- `qa_pair_embeddings` — Question/SQL pairs
- `doc_chunk_embeddings` — Documentation chunks

All vector search functionality has been removed from the current scope.

### 2.5 Query History Store (PostgreSQL, Append-Only)

#### `query_logs`
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | |
| `tenant_id` | UUID | |
| `user_id` | UUID | |
| `session_id` | UUID | Query session for conversation context |
| `natural_language_query` | TEXT | Original NL question |
| `generated_sql` | TEXT | SQL produced by NL2SQL |
| `final_sql` | TEXT | SQL actually executed (may differ if user edited) |
| `database_id` | UUID FK → databases | Target database |
| `model_tier` | VARCHAR(50) | Which model tier handled it (sqlcoder, qwen, deepseek, gpt4) |
| `model_used` | VARCHAR(100) | Specific model name+version |
| `execution_time_ms` | INTEGER | Database execution time |
| `total_latency_ms` | INTEGER | End-to-end latency |
| `row_count` | INTEGER | Result row count |
| `cost_usd` | DECIMAL(10,8) | Estimated inference + execution cost |
| `error` | TEXT | Error message if execution failed |
| `policy_results` | JSONB | Array of policy enforcement layer results |
| `user_rating` | SMALLINT | -1 (wrong), 0 (unrated), 1 (correct) |
| `user_correction` | TEXT | User's corrected SQL if different |
| `created_at` | TIMESTAMPTZ | |

**Partitioning**: By `created_at` (monthly). Auto-drop partitions older than retention period.

### 2.6 Feedback Store (PostgreSQL)

#### `feedback`
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | |
| `query_log_id` | UUID FK → query_logs | |
| `tenant_id` | UUID | |
| `user_id` | UUID | |
| `feedback_type` | ENUM | correction, approval, rating, comment |
| `original_sql` | TEXT | SQL before correction |
| `corrected_sql` | TEXT | SQL after correction |
| `rating` | SMALLINT | 1-5 |
| `comment` | TEXT | Free text |
| `validated` | BOOLEAN | Passed quality checks |
| `created_at` | TIMESTAMPTZ | |

### 2.7 Configuration Store (PostgreSQL)

#### `tenants`
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | |
| `name` | VARCHAR(255) | Company name |
| `tier` | ENUM | free, starter, pro, enterprise |
| `status` | ENUM | active, trialing, suspended, cancelled |
| `settings` | JSONB | Feature flags, preferences |
| `created_at` | TIMESTAMPTZ | |

#### `rbac_policies`
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | |
| `tenant_id` | UUID | |
| `role_name` | VARCHAR(100) | e.g., `analyst`, `business_user`, `admin` |
| `table_access` | JSONB | List of table IDs with access level (read, restricted, denied) |
| `column_mask` | JSONB | List of column IDs to mask/hide per role |
| `query_limit` | INTEGER | Max queries per month |
| `cost_limit` | DECIMAL(10,2) | Max query cost per month |
| `created_at` | TIMESTAMPTZ | |

#### `users`
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | |
| `tenant_id` | UUID | |
| `email` | VARCHAR(255) | |
| `role` | VARCHAR(50) FK → rbac_policies | |
| `external_id` | VARCHAR(255) | SSO provider user ID |
| `preferences` | JSONB | UI preferences, default DB |
| `created_at` | TIMESTAMPTZ | |

### 2.8 Metric Store (PostgreSQL)

#### `metric_definitions`
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | |
| `tenant_id` | UUID | |
| `name` | VARCHAR(255) | Metric name |
| `description` | TEXT | Business description |
| `formula` | TEXT | SQL expression or description |
| `data_type` | ENUM | currency, percentage, count, ratio |
| `dimensions` | JSONB | Valid group-by dimensions |
| `owner` | VARCHAR(255) | |
| `refresh_cadence` | ENUM | realtime, hourly, daily, weekly, monthly |
| `created_at` | TIMESTAMPTZ | |

### 2.9 Audit Store (PostgreSQL, Append-Only, Immutable)

#### `audit_log`
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | |
| `tenant_id` | UUID | |
| `user_id` | UUID | |
| `action` | VARCHAR(100) | query_executed, policy_blocked, schema_updated, config_changed, feedback_submitted |
| `resource_type` | VARCHAR(50) | query, database, table, column, user, policy |
| `resource_id` | UUID | |
| `details` | JSONB | Action-specific payload |
| `ip_address` | INET | |
| `user_agent` | TEXT | |
| `trace_id` | UUID | Distributed tracing correlation |
| `created_at` | TIMESTAMPTZ | |

---

## 3. Knowledge Engine API

### 3.1 API Service

The Knowledge Engine API is a FastAPI service (port 8200) exposed to all internal components via service mesh (mTLS). It is NOT exposed to external clients directly — external clients go through the public API layer.

### 3.2 Core Endpoints

#### `POST /v1/resolve`

Resolve a business term to physical schema elements.

```jsonc
// Request
{
  "tenant_id": "uuid",
  "term": "monthly recurring revenue",
  "context": {
    "database_ids": ["uuid1", "uuid2"],  // optional scope
    "user_role": "analyst"
  }
}

// Response
{
  "resolutions": [
    {
      "business_term": {
        "id": "uuid",
        "term": "Monthly Recurring Revenue",
        "definition": "Sum of active subscription amounts..."
      },
      "mappings": [
        {
          "database_id": "uuid",
          "table": "subscriptions",
          "column": "amount",
          "filters": {"status": "active"},
          "confidence": 0.95,
          "mapping_type": "computed"
        }
      ]
    }
  ],
  "latency_ms": 45
}
```

#### `POST /v1/retrieve`

Semantic search over knowledge stores.

```jsonc
// Request
{
  "tenant_id": "uuid",
  "query": "revenue by region for Q2 2026",
  "query_embedding": [0.1, 0.2, ...],  // optional, computed server-side if omitted
  "stores": ["schema", "qa_pairs", "doc_chunks"],
  "top_k": 10,
  "filters": {
    "database_ids": ["uuid"],
    "data_types": ["numeric", "timestamp"],
    "min_confidence": 0.5
  }
}

// Response
{
  "results": [
    {
      "store": "schema",
      "score": 0.89,
      "payload": {
        "table_id": "uuid",
        "table_name": "revenue",
        "column_name": "amount",
        "description": "Net revenue after discount",
        "data_type": "numeric"
      }
    },
    {
      "store": "qa_pairs",
      "score": 0.82,
      "payload": {
        "question": "show me revenue by region",
        "sql": "SELECT region, SUM(amount) FROM revenue GROUP BY region",
        "accuracy": 0.95
      }
    }
  ],
  "latency_ms": 35
}
```

#### `POST /v1/ingest`

Ingest knowledge from a source.

```jsonc
// Request
{
  "tenant_id": "uuid",
  "source_type": "ddl_introspection",
  "source_id": "uuid",  // database_id
  "data": {
    "tables": [
      {
        "table_name": "orders",
        "schema_name": "public",
        "columns": [
          {"name": "id", "type": "integer", "nullable": false, "is_pk": true},
          {"name": "customer_id", "type": "integer", "nullable": false},
          {"name": "amount", "type": "decimal(10,2)", "nullable": false}
        ]
      }
    ]
  }
}

// Response
{
  "ingestion_id": "uuid",
  "tables_ingested": 5,
  "columns_ingested": 42,
  "relationships_detected": 3,
  "enrichment_queued": true,
  "latency_ms": 1200
}
```

#### `POST /v1/store`

Persist arbitrary knowledge (feedback, queries, audit events).

```jsonc
// Request
{
  "tenant_id": "uuid",
  "store": "query_log",
  "data": {
    "user_id": "uuid",
    "natural_language_query": "show me revenue by month",
    "generated_sql": "SELECT ...",
    "database_id": "uuid",
    "execution_time_ms": 150,
    "cost_usd": 0.0042
  }
}

// Response
{
  "id": "uuid",
  "latency_ms": 5
}
```

#### `POST /v1/query`

Structured query over knowledge stores (internal use).

```jsonc
// Request
{
  "tenant_id": "uuid",
  "store": "schema",
  "query": {
    "select": ["tables.id", "tables.table_name", "columns.column_name"],
    "filters": {
      "database_id": "uuid",
      "is_pii": true
    },
    "order_by": ["tables.table_name ASC", "columns.ordinal_position ASC"],
    "limit": 100
  }
}

// Response
{
  "rows": [
    {"table_id": "uuid", "table_name": "users", "column_name": "email"},
    {"table_id": "uuid", "table_name": "users", "column_name": "ssn"}
  ],
  "latency_ms": 3
}
```

#### `POST /v1/refresh`

Refresh/enrich knowledge for a scope.

```jsonc
// Request
{
  "tenant_id": "uuid",
  "scope": {
    "database_id": "uuid",
    "refresh_types": ["descriptions", "embeddings", "relationships"]
  }
}

// Response
{
  "refresh_id": "uuid",
  "descriptions_generated": 12,
  "relationships_found": 2,
  "estimated_completion_s": 30
}
```

### 3.3 Internal gRPC Endpoints

For high-throughput operations, gRPC is used between components within the same cluster:

| gRPC Service | Methods | Transport |
|-------------|---------|-----------|
| `KnowledgeEngine` | `Resolve`, `Retrieve`, `Store` | mTLS gRPC |
| `Ingestion` | `IngestSchemas`, `IngestQueryLog`, `IngestFeedback` | mTLS gRPC |
| `Refresh` | `RefreshDatabase`, `RefreshAll` | mTLS gRPC |

---

## 4. Knowledge Lifecycle

### 4.1 Ingestion Pipeline

```
Source Event ──► Ingestion Queue ──► Pipeline Worker ──► Knowledge Engine
                                         │
                               ┌─────────┼─────────┐
                               │         │         │
                               ▼         ▼         ▼
                          Schema      (Embedding   Business
                          Store       Index —      Graph
                                      removed)
```

### 4.2 Enrichment Pipeline

```
Raw Schema ──► Description Generator (LLM) ──► Relationship Inference
                                                     │
                                           ┌─────────┴─────────┐
                                           ▼                   ▼
                                    Schema Store          (Vector Index
                                    (updated)              removed)
```

### 4.3 Refresh Triggers

| Trigger | Action | Cadence |
|---------|--------|---------|
| Database connected | Full schema introspection + enrichment | On connect |
| Scheduled refresh | Incremental schema update (new tables/columns) | Daily |
| Query executed | Query stored in history store | Real-time |
| Feedback submitted | Feedback stored; enrichment queue notified | Real-time |
| Accuracy threshold breached | Trigger full context layer refresh | Event-driven |
| Manual trigger | Admin-initiated refresh | On demand |

### 4.4 Data Retention

| Store | Retention | Cleanup Strategy |
|-------|-----------|-------------------|
| Schema Store | Indefinite | Soft delete on disconnect |
| Vector Index (removed) | Indefinite | Was rebuilt on refresh |
| Query History | 12 months (Pro), 24 months (Enterprise) | Partition drop |
| Feedback | Indefinite | — |
| Audit Log | 12 months (SOC 2 minimum) | Partition drop / archive |
| Configuration | Indefinite | — |

---

## 5. Consistency & Performance

### 5.1 Consistency Model

| Operation | Consistency | Rationale |
|-----------|-------------|-----------|
| Schema reads | Read-after-write for same tenant | Schema changes are infrequent; consistency matters |
| Query history writes | Eventual (async) | Query logging must not block user response |
| Feedback writes | Strong | Feedback must be immediately available for learning |
| Audit writes | Strong + durable | Immutable, must survive crashes |
| Vector index reads (removed) | Eventually consistent | Was: slight staleness acceptable for semantic search |
| Vector index writes (removed) | Async batch | Was: embedding generation is compute-intensive |

### 5.2 Performance Budgets

| Operation | Target P95 | Target P99 |
|-----------|-----------|-----------|
| `resolve` | 100ms | 200ms |
| `retrieve` (vector — removed) | 50ms | 100ms |
| `retrieve` (structured) | 20ms | 50ms |
| `ingest` (DDL, 100 tables) | 30s | 60s |
| `store` (query log) | 10ms | 25ms |
| `store` (audit) | 15ms | 30ms |
| `refresh` (enrichment, 100 tables) | 60s | 120s |

### 5.3 Caching Strategy

| Cache | What | TTL | Invalidation |
|-------|------|-----|-------------|
| Schema metadata (removed — was Redis) | Table/column lists per database | 60s | On schema change event |
| Business term resolution (removed — was Redis) | Term → column mappings | 300s | On term update event |
| Embedding cache (in-memory, removed) | Frequent query embeddings | 60s | LRU eviction |
| RBAC policies (removed — was Redis) | User → permissions | 60s | On policy change event |

---

## 6. Dependencies & External Contracts

### 6.1 Stores the Knowledge Engine Depends On

| Store | Availability Requirement | Failure Mode |
|-------|--------------------------|--------------|
| PostgreSQL (primary) | High (HA cluster) | Read-only mode on failover; writes queued |
| Qdrant (removed) | High (HA cluster) | Was: degraded to keyword-only search |
| Redis (removed) | Medium | Was: schema queries fall back to PostgreSQL direct reads |

### 6.2 What the Knowledge Engine Provides to Components

| Component | Depends On | Guarantee |
|-----------|------------|-----------|
| Schema Intelligence | Write access to all stores | Schema writes are durable |
| Context Retriever | Read access to schema + history | Retrieval latency < 100ms P95 |
| Query Planner | Read access to graph + metrics + schema | Resolution latency < 100ms P95 |
| NL2SQL Generator | Read access to context (via Retriever) | Context packaged in < 200ms |
| Guardrail Stack | Read access to schema + config + audit | Policy checks < 50ms |
| Executor | Write access to history + audit | Writes are non-blocking (async) |
| Learning Loop | Read/write access to all stores | Bulk operations, not latency-sensitive |
| API Layer | Indirect access via Knowledge Engine API | Standard web latency |

---

## 7. References

| Source | Relevance |
|--------|-----------|
| [System-Architecture.md](./System-Architecture.md) | Knowledge Engine's role in overall architecture |
| [Component-Design.md](./Component-Design.md) | How each component implements Knowledge Engine contracts |
| [Data-Flow.md](./Data-Flow.md) | How knowledge moves through the system |
| [API-Design.md](./API-Design.md) | Public API mappings to Knowledge Engine operations |
| [Technology-Recommendations.md](../Technical-Landscape/Technology-Recommendations.md) | Technology selection for each store |
