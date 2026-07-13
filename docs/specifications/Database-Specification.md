# Database Specification

**Version**: 1.0.0 | **Status**: Approved | **Last Updated**: 2026-07-10

**Document Owner**: Principal Database Architect

**Cross-References**:
- [KnowledgeEngine-Specification.md](KnowledgeEngine-Specification.md) — KE store schemas, migration patterns
- [API-Specification.md](API-Specification.md) — Query history, audit, feedback API endpoints
- [AI-Agent-Specification.md](AI-Agent-Specification.md) — QueryState persistence schema
- [Performance-Budgets.md](Performance-Budgets.md) — Database query latency budgets
- [Security-Specification.md](Security-Specification.md) — RLS policies, encryption at rest
- [Infrastructure-Specification.md](Infrastructure-Specification.md) — PostgreSQL deployment, connection pooling

---

## Table of Contents

1. [Overview](#1-overview)
2. [Naming Conventions](#2-naming-conventions)
3. [Entity Relationship Diagram](#3-entity-relationship-diagram)
4. [Tenants Store](#4-tenants-store)
5. [Schema Store](#5-schema-store)
6. [Graph Store](#6-graph-store)
7. [History Store](#7-history-store)
8. [Feedback Store](#8-feedback-store)
9. [Config Store](#9-config-store)
10. [Metrics Store](#10-metrics-store)
11. [Audit Store](#11-audit-store)
12. [Job Queue Store](#12-job-queue-store)
13. [Tenant Isolation Strategy](#15-tenant-isolation-strategy)
16. [Partitioning Strategy](#16-partitioning-strategy)
17. [Backup & Recovery Strategy](#17-backup--recovery-strategy)
18. [Retention Policies](#18-retention-policies)
19. [Scaling Strategy](#19-scaling-strategy)
20. [Migration Strategy](#20-migration-strategy)
21. [Soft Delete Strategy](#21-soft-delete-strategy)
22. [Future Evolution](#22-future-evolution)

---

## 1. Overview

### Stores Matrix

| Store | Engine | Location | Data Type | Tenant Isolation | Scale |
|-------|--------|----------|-----------|-----------------|-------|
| Tenants | PostgreSQL | ke_db.tenants | Relational | Global (no tenant_id) | < 10K rows |
| Schema | PostgreSQL | ke_db.schema_store | Relational | RLS (via join) | 100M+ rows |
| Graph | PostgreSQL | ke_db.graph_store | Graph (CTE) | RLS (direct) | 200M+ rows |
| History | PostgreSQL | ke_db.history_store | Time-series | RLS (direct) | 1B+ rows |
| Feedback | PostgreSQL | ke_db.feedback_store | Relational | RLS (direct) | 50M+ rows |
| Config | PostgreSQL | ke_db.config_store | Key-value | RLS (nullable) | < 100K rows |
| Metrics | PostgreSQL | ke_db.metrics_store | Time-series | Column tag | 500M+ rows |
| Audit | PostgreSQL | ke_db.audit_store | Time-series | RLS (direct) | 1B+ rows |
| Jobs | PostgreSQL | ke_db.job_queue | Relational | RLS (direct) | 10M+ rows |
| Vector | Qdrant | tenant_{id}_embeddings | Vector | Collection-per-tenant | 200M+ vectors |
| Cache | Redis | db 0-3 | Key-value | Key prefix | < 10GB |
| Rate Limit | Redis | db 4 | Counter | Key prefix | < 1GB |
| Idempotency | Redis | db 5 | Key-value (TTL) | Key prefix | < 1GB |
| Sessions | Redis | db 6 | Key-value (TTL) | Key prefix | < 500MB |

### Connection Architecture

```
                    ┌───────────────┐
                    │   PgBouncer    │  (connection pooling, transaction mode)
                    └───────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
      ┌─────────────┐ ┌─────────┐ ┌─────────────┐
      │  PostgreSQL  │ │  Redis  │ │   Qdrant    │
      │  (primary)   │ │ (cache) │ │  (vectors)  │
      └─────────────┘ └─────────┘ └─────────────┘
```

---

## 2. Naming Conventions

### 2.1 General Rules

| Category | Convention | Example |
|----------|-----------|---------|
| Database names | `snake_case`, descriptive | `ke_production` |
| Schema names | `snake_case` | `schema_store`, `graph_store` |
| Table names | `snake_case`, plural nouns | `schema_tables`, `graph_edges` |
| Column names | `snake_case`, descriptive | `created_at`, `tenant_id` |
| Primary keys | `id` (UUID) | `id UUID PRIMARY KEY DEFAULT gen_random_uuid()` |
| Foreign keys | `{referenced_table_singular}_id` | `tenant_id`, `database_id`, `table_id` |
| Index names | `idx_{table}_{column}[suffix]` | `idx_schema_tables_tenant`, `idx_query_history_created` |
| Unique constraints | `uq_{table}_{columns}` | `uq_tenants_slug` |
| Foreign key constraints | `fk_{table}_{referenced_table}` | `fk_tables_schema` |
| Check constraints | `ck_{table}_{rule}` | `ck_feedback_rating` |
| Sequence names | `seq_{table}_{column}` | `seq_schema_version` |
| Partition names | `{table}_y{year}m{month}` | `query_history_y2026m07` |

### 2.2 Column Naming Rules

| Column Pattern | Type | Convention |
|----------------|------|------------|
| Primary key | UUID | Always `id` |
| Tenant reference | UUID | Always `tenant_id` |
| Foreign key | UUID | `{entity}_id` (e.g., `database_id`) |
| Timestamp (created) | TIMESTAMPTZ | Always `created_at` |
| Timestamp (updated) | TIMESTAMPTZ | Always `updated_at` |
| Soft delete | TIMESTAMPTZ | Always `deleted_at` |
| Status | VARCHAR(50) | Always `status` |
| Version number | INTEGER | Always `version` |
| Boolean flags | BOOLEAN | Prefix with `is_` (e.g., `is_active`, `is_primary_key`) |
| JSON data | JSONB | Always `properties` or `{context}_json` |
| Descriptions | TEXT | Always `description` |
| Names | VARCHAR(255) | Always `name` |

---

## 3. Entity Relationship Diagram

### 3.1 Core Schema (Text ERD)

```
tenants 1──N databases 1──N schema_infos 1──N tables 1──N columns
  │                                                  │
  │                                                  │ (optional)
  │                                                  ▼
  └──────────────────────────────────────── relationships
  │
  │ 1──N query_history
  │ 1──N feedback
  │ 1──N audit_log
  │ 1──N graph_nodes 1──N graph_edges
  │ 1──N jobs
```

### 3.2 Store Groupings

```
┌─────────────────────────────────────────────────────────┐
│                    ke_db (PostgreSQL)                     │
│                                                          │
│  tenants ──── schema_store ──── graph_store              │
│  (global)    (tenants.schemas)  (tenants.graph)          │
│                                                          │
│  history_store ── feedback_store ── config_store         │
│  (tenants.hist)  (tenants.fb)      (tenants.cfg)         │
│                                                          │
│  metrics_store ── audit_store ──── job_queue             │
│  (tenants.met)   (tenants.audit)   (tenants.jobs)        │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│              tenant_{id}_embeddings (Qdrant)              │
│  One collection per tenant                               │
│  Content types: schema_element, query, business_term     │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                     Redis Instances                       │
│  db 0: Query cache        (prefix: cache:{tenant}:{hash}) │
│  db 1: Rate limit         (prefix: rl:{tenant}:{key})    │
│  db 2: Idempotency        (prefix: idem:{key})           │
│  db 3: Sessions           (prefix: sess:{token})         │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Tenants Store

**Schema**: `public` | **Table**: `tenants` | **Purpose**: Global tenant registry. Every row = one customer organization.

### 4.1 Table Definition

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| `id` | UUID | PK | `gen_random_uuid()` | Unique tenant identifier |
| `name` | VARCHAR(255) | NOT NULL | — | Company/organization name |
| `slug` | VARCHAR(100) | NOT NULL, UNIQUE | — | URL-friendly identifier (e.g., `acme-corp`) |
| `tier` | VARCHAR(50) | NOT NULL, DEFAULT 'starter' | `'starter'` | Plan tier: `free`, `starter`, `pro`, `enterprise` |
| `status` | VARCHAR(50) | NOT NULL, DEFAULT 'active' | `'active'` | `active`, `suspended`, `deleting`, `deleted` |
| `settings` | JSONB | DEFAULT '{}' | `'{}'` | Tenant-level configuration overrides |
| `features` | JSONB | DEFAULT '{}' | `'{}'` | Enabled feature flags |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | Row creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | Row last update timestamp |
| `deleted_at` | TIMESTAMPTZ | — | NULL | Soft delete timestamp |

### 4.2 Indexes

```sql
CREATE UNIQUE INDEX uq_tenants_slug ON tenants(slug) WHERE deleted_at IS NULL;
CREATE INDEX idx_tenants_tier ON tenants(tier) WHERE deleted_at IS NULL;
CREATE INDEX idx_tenants_status ON tenants(status);
```

### 4.3 Constraints

```sql
ALTER TABLE tenants ADD CONSTRAINT ck_tenants_tier
    CHECK (tier IN ('free', 'starter', 'pro', 'enterprise'));
ALTER TABLE tenants ADD CONSTRAINT ck_tenants_status
    CHECK (status IN ('active', 'suspended', 'deleting', 'deleted'));
ALTER TABLE tenants ADD CONSTRAINT ck_tenants_slug_format
    CHECK (slug ~* '^[a-z0-9]([a-z0-9-]*[a-z0-9])?$');
```

### 4.4 Relationships

| Parent | Child | Type | FK Column | On Delete |
|--------|-------|------|-----------|-----------|
| tenants | databases | 1:N | tenant_id | CASCADE |
| tenants | query_history | 1:N | tenant_id | CASCADE |
| tenants | feedback | 1:N | tenant_id | CASCADE |
| tenants | audit_log | 1:N | tenant_id | CASCADE |
| tenants | graph_nodes | 1:N | tenant_id | CASCADE |
| tenants | graph_edges | 1:N | tenant_id | CASCADE |
| tenants | jobs | 1:N | tenant_id | CASCADE |

### 4.5 Partitioning

None. This table is small (< 10,000 rows even at 10K tenants).

### 4.6 Migration Strategy

- Alembic migration `0001_create_tenants.py`
- Data migration for seed tenant: none (created via API)

### 4.7 Soft Deletes

- Use `deleted_at` timestamp
- All queries filter `WHERE deleted_at IS NULL` (or use a view)
- Unique constraints include `WHERE deleted_at IS NULL` to allow re-registration
- Hard delete after 30-day grace period (cron job)

### 4.8 Tenant Isolation

Global table. No `tenant_id` column. Accessible only by system admins.

### 4.9 Backup Strategy

Included in full database backup (daily). Individual tenant export available on request.

### 4.10 Retention Policy

Permanent. Tenants are soft-deleted only. Hard delete 30 days after soft delete.

### 4.11 Scaling Strategy

- Single table, no partitioning needed
- Read replicas for admin dashboard queries
- Connection pooling via PgBouncer

### 4.12 Future Evolution

| Change | Timeline | Impact |
|--------|----------|--------|
| Add `billing_provider_id` | V1 | New nullable column |
| Add `mfa_enabled` | V1 | New boolean column |
| Add `data_region` for GDPR | V1 | New VARCHAR column |
| Split into `organizations` + `workspaces` | Year 2 | New table, migration |

---

## 5. Schema Store

### 5.1 databases

**Schema**: `schema_store` | **Table**: `databases` | **Purpose**: Registered database connections per tenant.

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| `id` | UUID | PK | `gen_random_uuid()` | Unique ID |
| `tenant_id` | UUID | NOT NULL, FK → tenants(id) | — | Owning tenant |
| `name` | VARCHAR(255) | NOT NULL | — | Display name |
| `db_type` | VARCHAR(50) | NOT NULL | — | `postgresql`, `mysql`, `snowflake`, `bigquery`, `duckdb` |
| `connection_hash` | VARCHAR(64) | NOT NULL | — | SHA-256 of normalized connection string (for dedup) |
| `host` | VARCHAR(255) | — | NULL | Database host (not stored for cloud DBs) |
| `port` | INTEGER | — | NULL | Database port |
| `database_name` | VARCHAR(255) | — | NULL | Target database name |
| `username` | VARCHAR(255) | — | NULL | Connection username |
| `schema_filter` | TEXT[] | — | NULL | Array of schemas to sync (NULL = all) |
| `ssl_enabled` | BOOLEAN | NOT NULL | TRUE | SSL requirement |
| `connection_options` | JSONB | DEFAULT '{}' | `'{}'` | Timeout, pool size, extra params |
| `sync_status` | VARCHAR(50) | NOT NULL | `'pending'` | `pending`, `syncing`, `synced`, `error` |
| `sync_error_message` | TEXT | — | NULL | Last sync error detail |
| `last_synced_at` | TIMESTAMPTZ | — | NULL | Last successful sync timestamp |
| `table_count` | INTEGER | DEFAULT 0 | 0 | Cached table count |
| `is_active` | BOOLEAN | NOT NULL | TRUE | Soft disable without deleting |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | — |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | — |
| `deleted_at` | TIMESTAMPTZ | — | NULL | Soft delete |

**Indexes**:
```sql
CREATE INDEX idx_databases_tenant ON databases(tenant_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_databases_type ON databases(db_type) WHERE deleted_at IS NULL;
CREATE INDEX idx_databases_status ON databases(sync_status);
CREATE INDEX idx_databases_conn_hash ON databases(connection_hash);
CREATE UNIQUE INDEX uq_databases_tenant_name ON databases(tenant_id, name) WHERE deleted_at IS NULL;
```

**Constraints**:
```sql
ALTER TABLE databases ADD CONSTRAINT ck_databases_type
    CHECK (db_type IN ('postgresql', 'mysql', 'snowflake', 'bigquery', 'duckdb'));
ALTER TABLE databases ADD CONSTRAINT ck_databases_sync_status
    CHECK (sync_status IN ('pending', 'syncing', 'synced', 'error'));
```

**Partitioning**: None (fewer than 100K rows).

**Soft Deletes**: `deleted_at` field. Data cascade-deleted after 7 days (config + history retained).

**Tenant Isolation**: RLS via `tenant_id`.

---

### 5.2 schema_infos

**Schema**: `schema_store` | **Table**: `schema_infos` | **Purpose**: Database schemas (logical groupings like `public`, `sales`).

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| `id` | UUID | PK | `gen_random_uuid()` | — |
| `database_id` | UUID | NOT NULL, FK → databases(id) | — | Parent database |
| `name` | VARCHAR(255) | NOT NULL | — | Schema name (e.g., `public`) |
| `raw_ddl` | TEXT | — | NULL | Full DDL snapshot |
| `version` | INTEGER | NOT NULL | 1 | Version counter, incremented on DDL change |
| `table_count` | INTEGER | DEFAULT 0 | 0 | Cached table count |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | — |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | — |

**Indexes**:
```sql
CREATE INDEX idx_schema_infos_database ON schema_infos(database_id);
CREATE UNIQUE INDEX uq_schema_infos_db_name ON schema_infos(database_id, name);
```

**Partitioning**: None.

**Tenant Isolation**: Inherited via `database_id → databases.tenant_id`. RLS policy joins through databases table.

---

### 5.3 tables

**Schema**: `schema_store` | **Table**: `tables` | **Purpose**: Individual database tables with metadata.

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| `id` | UUID | PK | `gen_random_uuid()` | — |
| `schema_id` | UUID | NOT NULL, FK → schema_infos(id) | — | Parent schema |
| `name` | VARCHAR(255) | NOT NULL | — | Table name |
| `description` | TEXT | — | NULL | LLM-generated business description |
| `ddl` | TEXT | — | NULL | Raw CREATE TABLE DDL |
| `row_estimate` | BIGINT | DEFAULT 0 | 0 | Estimated row count (from DB stats) |
| `version` | INTEGER | NOT NULL | 1 | Incremented on column/DDL change |
| `is_active` | BOOLEAN | NOT NULL | TRUE | False = table dropped or deprecated |
| `last_introspected_at` | TIMESTAMPTZ | — | NULL | Last time schema was read from target DB |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | — |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | — |

**Indexes**:
```sql
CREATE INDEX idx_tables_schema ON tables(schema_id);
CREATE INDEX idx_tables_active ON tables(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_tables_updated ON tables(updated_at);
CREATE INDEX idx_tables_name_search ON tables USING gin(name gin_trgm_ops);
CREATE UNIQUE INDEX uq_tables_schema_name ON tables(schema_id, name);
```

**Partitioning**: None. Growth is bounded by schema size (~500 tables per schema).

**Tenant Isolation**: Inherited via `schema_id → schema_infos.database_id → databases.tenant_id`.

---

### 5.4 columns

**Schema**: `schema_store` | **Table**: `columns` | **Purpose**: Column-level metadata. This is the most detailed and heavily queried table.

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| `id` | UUID | PK | `gen_random_uuid()` | — |
| `table_id` | UUID | NOT NULL, FK → tables(id) | — | Parent table |
| `name` | VARCHAR(255) | NOT NULL | — | Column name |
| `ordinal_position` | INTEGER | NOT NULL | — | Column order in table (1-indexed) |
| `data_type` | VARCHAR(100) | NOT NULL | — | Native DB data type (e.g., `varchar(255)`, `decimal(10,2)`) |
| `is_nullable` | BOOLEAN | NOT NULL | TRUE | NULL constraint |
| `is_primary_key` | BOOLEAN | NOT NULL | FALSE | Part of primary key |
| `is_unique` | BOOLEAN | NOT NULL | FALSE | Has unique constraint |
| `default_value` | TEXT | — | NULL | Column default expression |
| `description` | TEXT | — | NULL | LLM-generated business description |
| `foreign_key_table` | VARCHAR(255) | — | NULL | Referenced table name |
| `foreign_key_column` | VARCHAR(255) | — | NULL | Referenced column name |
| `ordinal_position` | INTEGER | NOT NULL | — | Column order |
| `character_maximum_length` | INTEGER | — | NULL | For varchar/char types |
| `numeric_precision` | INTEGER | — | NULL | For numeric/decimal types |
| `numeric_scale` | INTEGER | — | NULL | For numeric/decimal types |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | — |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | — |

**Indexes**:
```sql
CREATE INDEX idx_columns_table ON columns(table_id);
CREATE INDEX idx_columns_pk ON columns(table_id) WHERE is_primary_key = TRUE;
CREATE INDEX idx_columns_fk ON columns(foreign_key_table, foreign_key_column)
    WHERE foreign_key_table IS NOT NULL;
CREATE INDEX idx_columns_name_search ON columns USING gin(name gin_trgm_ops);
CREATE INDEX idx_columns_data_type ON columns(data_type);
CREATE UNIQUE INDEX uq_columns_table_name ON columns(table_id, name);
```

**Partitioning**: None. Growth per tenant: ~10K columns. 10K tenants × 10K columns = 100M rows. Monitor carefully.

**Migration Strategy**: Add partitioning by `table_id` hash if > 500M rows.

---

### 5.5 relationships

**Schema**: `schema_store` | **Table**: `relationships` | **Purpose**: Foreign key and inferred relationships between tables.

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| `id` | UUID | PK | `gen_random_uuid()` | — |
| `tenant_id` | UUID | NOT NULL, FK → tenants(id) | — | Direct tenant ID for RLS |
| `source_table_id` | UUID | NOT NULL, FK → tables(id) | — | Source (child) table |
| `source_column` | VARCHAR(255) | NOT NULL | — | Source column name |
| `target_table_id` | UUID | NOT NULL, FK → tables(id) | — | Target (parent) table |
| `target_column` | VARCHAR(255) | NOT NULL | — | Target column name |
| `relationship_type` | VARCHAR(50) | NOT NULL | `'foreign_key'` | `foreign_key`, `inferred`, `semantic` |
| `confidence` | REAL | NOT NULL | 1.0 | 0.0-1.0 confidence score |
| `discovered_by` | VARCHAR(100) | NOT NULL | `'connector'` | `connector`, `inferer`, `llm`, `manual` |
| `properties` | JSONB | DEFAULT '{}' | `'{}'` | Cardinality, direction hints |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | — |

**Indexes**:
```sql
CREATE INDEX idx_relationships_tenant ON relationships(tenant_id);
CREATE INDEX idx_relationships_source ON relationships(source_table_id);
CREATE INDEX idx_relationships_target ON relationships(target_table_id);
CREATE INDEX idx_relationships_type ON relationships(relationship_type);
CREATE UNIQUE INDEX uq_relationships_columns
    ON relationships(source_table_id, source_column, target_table_id, target_column);
```

**Constraints**:
```sql
ALTER TABLE relationships ADD CONSTRAINT ck_relationships_type
    CHECK (relationship_type IN ('foreign_key', 'inferred', 'semantic'));
ALTER TABLE relationships ADD CONSTRAINT ck_relationships_confidence
    CHECK (confidence >= 0.0 AND confidence <= 1.0);
```

**Partitioning**: None.

**Tenant Isolation**: Direct `tenant_id` column with RLS.

---

## 6. Graph Store

### 6.1 graph_nodes

**Schema**: `graph_store` | **Table**: `graph_nodes` | **Purpose**: Business ontology nodes — tables, columns, domains, concepts, query patterns.

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| `id` | UUID | PK | `gen_random_uuid()` | — |
| `tenant_id` | UUID | NOT NULL, FK → tenants(id) | — | Direct tenant ID for RLS |
| `node_type` | VARCHAR(50) | NOT NULL | — | `table`, `column`, `domain`, `concept`, `glossary_term`, `query_pattern` |
| `external_id` | VARCHAR(255) | — | NULL | References external entity ID (tables.id, columns.id) |
| `label` | VARCHAR(255) | NOT NULL | — | Human-readable label |
| `description` | TEXT | — | NULL | Business description |
| `properties` | JSONB | DEFAULT '{}' | `'{}'` | Type-specific properties |
| `embedding` | VECTOR(1024) | — | NULL | pgvector embedding for semantic search |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | — |

**Indexes**:
```sql
-- B-tree indexes
CREATE INDEX idx_graph_nodes_tenant ON graph_nodes(tenant_id);
CREATE INDEX idx_graph_nodes_type ON graph_nodes(node_type);
-- Trigram text search
CREATE INDEX idx_graph_nodes_label_search ON graph_nodes USING gin(label gin_trgm_ops);
-- pgvector (IVFFlat, lists=100 — tune based on data volume)
CREATE INDEX idx_graph_nodes_embedding ON graph_nodes
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
-- Composite for common query pattern
CREATE INDEX idx_graph_nodes_tenant_type ON graph_nodes(tenant_id, node_type);
```

**Constraints**:
```sql
ALTER TABLE graph_nodes ADD CONSTRAINT ck_graph_nodes_type
    CHECK (node_type IN ('table', 'column', 'domain', 'concept', 'glossary_term', 'query_pattern'));
```

**Partitioning**: By `tenant_id` hash (mod 16) if > 50M rows.

**Tenant Isolation**: Direct `tenant_id` column with RLS.

---

### 6.2 graph_edges

**Schema**: `graph_store` | **Table**: `graph_edges` | **Purpose**: Directed relationships between ontology nodes.

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| `id` | UUID | PK | `gen_random_uuid()` | — |
| `tenant_id` | UUID | NOT NULL, FK → tenants(id) | — | Direct tenant ID for RLS |
| `source_node_id` | UUID | NOT NULL, FK → graph_nodes(id) | — | Source node |
| `target_node_id` | UUID | NOT NULL, FK → graph_nodes(id) | — | Target node |
| `edge_type` | VARCHAR(50) | NOT NULL | — | `belongs_to`, `references`, `maps_to`, `frequently_joined`, `semantic_parent` |
| `weight` | REAL | NOT NULL | 1.0 | Edge weight for traversal scoring |
| `properties` | JSONB | DEFAULT '{}' | `'{}'` | Edge metadata |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | — |

**Indexes**:
```sql
CREATE INDEX idx_graph_edges_tenant ON graph_edges(tenant_id);
CREATE INDEX idx_graph_edges_source ON graph_edges(source_node_id);
CREATE INDEX idx_graph_edges_target ON graph_edges(target_node_id);
CREATE INDEX idx_graph_edges_type ON graph_edges(edge_type);
-- Composite for graph traversal
CREATE INDEX idx_graph_edges_source_type ON graph_edges(source_node_id, edge_type);
CREATE UNIQUE INDEX uq_graph_edges
    ON graph_edges(source_node_id, target_node_id, edge_type);
```

**Constraints**:
```sql
ALTER TABLE graph_edges ADD CONSTRAINT ck_graph_edges_type
    CHECK (edge_type IN ('belongs_to', 'references', 'maps_to', 'frequently_joined', 'semantic_parent'));
ALTER TABLE graph_edges ADD CONSTRAINT ck_graph_edges_weight
    CHECK (weight > 0);
ALTER TABLE graph_edges ADD CONSTRAINT ck_graph_edges_no_self_loop
    CHECK (source_node_id <> target_node_id);
```

**Partitioning**: By `tenant_id` hash.

**Tenant Isolation**: Direct `tenant_id` column with RLS.

---

## 7. History Store

### 7.1 query_history

**Schema**: `history_store` | **Table**: `query_history` | **Purpose**: Record of every query executed. Primary source for learning loop, audit, and usage analytics.

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| `id` | UUID | PK | `gen_random_uuid()` | — |
| `tenant_id` | UUID | NOT NULL, FK → tenants(id) | — | Direct tenant ID |
| `user_id` | VARCHAR(255) | NOT NULL | — | User identifier from auth |
| `database_id` | UUID | — | NULL | Target database |
| `conversation_id` | UUID | — | NULL | Conversation grouping |
| `natural_query` | TEXT | NOT NULL | — | Original NL query text |
| `generated_sql` | TEXT | — | NULL | SQL produced by pipeline |
| `executed_sql` | TEXT | — | NULL | SQL actually executed (may differ after repair) |
| `status` | VARCHAR(50) | NOT NULL | `'pending'` | `pending`, `processing`, `executing`, `success`, `failed`, `rejected`, `cancelled` |
| `error_code` | VARCHAR(50) | — | NULL | Error code if failed |
| `error_message` | TEXT | — | NULL | Error details if failed |
| `result_summary` | JSONB | DEFAULT '{}' | `'{}'` | Column names, row count, truncated flag |
| `row_count` | INTEGER | — | NULL | Number of result rows |
| `execution_time_ms` | INTEGER | — | NULL | DB execution time only |
| `total_time_ms` | INTEGER | — | NULL | End-to-end pipeline time |
| `model_used` | VARCHAR(100) | — | NULL | Final model tier used |
| `model_tier_attempted` | VARCHAR(100) | — | NULL | Initial model tier selected |
| `tokens_in` | INTEGER | — | NULL | LLM input tokens |
| `tokens_out` | INTEGER | — | NULL | LLM output tokens |
| `cost` | REAL | NOT NULL | 0.0 | Total query cost (USD) |
| `cost_breakdown` | JSONB | DEFAULT '{}' | `'{}'` | Per-stage cost breakdown |
| `policy_results` | JSONB | DEFAULT '[]' | `'[]'` | Per-layer policy result objects |
| `pipeline_breakdown_ms` | JSONB | DEFAULT '{}' | `'{}'` | Per-stage timing |
| `feedback_rating` | VARCHAR(20) | — | NULL | `positive`, `negative`, `partial`, `unrated` |
| `feedback_id` | UUID | — | NULL | Link to feedback if provided |
| `client_info` | JSONB | DEFAULT '{}' | `'{}'` | Client type, version, user agent |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | — |

**Indexes**:
```sql
-- Primary access patterns
CREATE INDEX idx_qh_tenant_created ON query_history(tenant_id, created_at DESC);
CREATE INDEX idx_qh_user ON query_history(tenant_id, user_id);
CREATE INDEX idx_qh_status ON query_history(tenant_id, status);
CREATE INDEX idx_qh_database ON query_history(database_id) WHERE database_id IS NOT NULL;
-- Analytics queries
CREATE INDEX idx_qh_cost ON query_history(tenant_id, cost);
CREATE INDEX idx_qh_exec_time ON query_history(tenant_id, execution_time_ms);
CREATE INDEX idx_qh_model ON query_history(model_used);
-- Full-text search
CREATE INDEX idx_qh_query_search ON query_history
    USING gin(to_tsvector('english', natural_query));
-- Learning loop queries
CREATE INDEX idx_qh_feedback_pending ON query_history(tenant_id, feedback_rating)
    WHERE feedback_rating IS NULL;
```

**Constraints**:
```sql
ALTER TABLE query_history ADD CONSTRAINT ck_qh_status
    CHECK (status IN ('pending','processing','executing','success','failed','rejected','cancelled'));
ALTER TABLE query_history ADD CONSTRAINT ck_qh_cost
    CHECK (cost >= 0);
ALTER TABLE query_history ADD CONSTRAINT ck_qh_feedback_rating
    CHECK (feedback_rating IN ('positive','negative','partial','unrated') OR feedback_rating IS NULL);
```

**Partitioning**: By month on `created_at`. See §16 for partition schema.

**Retention**: 12 months. Partitions older than 12 months are dropped.

**Tenant Isolation**: Direct `tenant_id` column with RLS.

---

## 8. Feedback Store

### 8.1 feedback

**Schema**: `feedback_store` | **Table**: `feedback` | **Purpose**: User feedback on query results. Drives the learning loop.

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| `id` | UUID | PK | `gen_random_uuid()` | — |
| `tenant_id` | UUID | NOT NULL, FK → tenants(id) | — | Direct tenant ID |
| `query_id` | UUID | NOT NULL, FK → query_history(id) | — | Associated query |
| `user_id` | VARCHAR(255) | NOT NULL | — | User who submitted feedback |
| `rating` | VARCHAR(20) | NOT NULL | — | `positive`, `negative`, `partial` |
| `corrected_sql` | TEXT | — | NULL | User-provided corrected SQL |
| `comment` | TEXT | — | NULL | Free-text comment |
| `category` | VARCHAR(50) | — | NULL | `wrong_sql`, `wrong_results`, `slow`, `wrong_context`, `other` |
| `feedback_token` | VARCHAR(100) | — | NULL | Anti-abuse token from query response |
| `processed` | BOOLEAN | NOT NULL | FALSE | Processed by learning loop |
| `quality_score` | REAL | — | NULL | Learning loop quality rating (0.0-1.0) |
| `processing_result` | JSONB | DEFAULT '{}' | `'{}'` | Learning loop processing metadata |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | — |

**Indexes**:
```sql
CREATE INDEX idx_feedback_tenant ON feedback(tenant_id);
CREATE INDEX idx_feedback_query ON feedback(query_id);
CREATE INDEX idx_feedback_unprocessed ON feedback(tenant_id, processed, created_at)
    WHERE processed = FALSE;
CREATE INDEX idx_feedback_rating ON feedback(rating);
CREATE INDEX idx_feedback_category ON feedback(category) WHERE category IS NOT NULL;
CREATE UNIQUE INDEX uq_feedback_query_user ON feedback(query_id, user_id);
```

**Constraints**:
```sql
ALTER TABLE feedback ADD CONSTRAINT ck_feedback_rating
    CHECK (rating IN ('positive', 'negative', 'partial'));
ALTER TABLE feedback ADD CONSTRAINT ck_feedback_quality_score
    CHECK (quality_score IS NULL OR (quality_score >= 0.0 AND quality_score <= 1.0));
```

**Partitioning**: By month on `created_at`.

**Retention**: Permanent (soft-delete only).

**Tenant Isolation**: Direct `tenant_id` column with RLS.

---

## 9. Config Store

### 9.1 config

**Schema**: `config_store` | **Table**: `config` | **Purpose**: Key-value configuration store with multi-scope support.

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| `id` | UUID | PK | `gen_random_uuid()` | — |
| `scope` | VARCHAR(50) | NOT NULL | `'tenant'` | `global`, `tenant`, `user` |
| `scope_id` | VARCHAR(255) | — | NULL | ID of the scope entity (tenant_id, user_id, or NULL for global) |
| `key` | VARCHAR(255) | NOT NULL | — | Configuration key name |
| `value` | JSONB | NOT NULL | — | Configuration value (supports any JSON type) |
| `description` | TEXT | — | NULL | Human-readable description |
| `is_secret` | BOOLEAN | NOT NULL | FALSE | If true, value is masked in responses |
| `version` | INTEGER | NOT NULL | 1 | Incremented on update |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | — |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | — |

**Indexes**:
```sql
CREATE UNIQUE INDEX uq_config_scope_key ON config(scope, scope_id, key);
CREATE INDEX idx_config_scope ON config(scope);
CREATE INDEX idx_config_scope_id ON config(scope_id) WHERE scope_id IS NOT NULL;
```

**Partitioning**: None. Very small table.

**Tenant Isolation**: RLS allows:
- `scope = 'global'` rows visible to all
- `scope = 'tenant' AND scope_id = current_tenant_id` visible to that tenant
- `scope = 'user'` visible to that user only

---

## 10. Metrics Store

### 10.1 metrics

**Schema**: `metrics_store` | **Table**: `metrics` | **Purpose**: Time-series metrics for observability, billing, and analytics.

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| `id` | UUID | PK | `gen_random_uuid()` | — |
| `tenant_id` | UUID | — | NULL | Tenant context (nullable for global metrics) |
| `metric_name` | VARCHAR(255) | NOT NULL | — | Metric identifier (dot-separated, e.g., `pipeline.query.latency_ms`) |
| `value` | DOUBLE PRECISION | NOT NULL | — | Metric value |
| `tags` | JSONB | DEFAULT '{}' | `'{}'` | Metric dimensions (model, status, stage, etc.) |
| `recorded_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | Metric timestamp |

**Indexes**:
```sql
CREATE INDEX idx_metrics_name_time ON metrics(metric_name, recorded_at DESC);
CREATE INDEX idx_metrics_tenant_time ON metrics(tenant_id, recorded_at DESC);
-- GIN index for tag queries
CREATE INDEX idx_metrics_tags ON metrics USING gin(tags);
-- Composite for common queries
CREATE INDEX idx_metrics_name_tenant_time
    ON metrics(metric_name, tenant_id, recorded_at DESC);
```

**Constraints**:
```sql
ALTER TABLE metrics ADD CONSTRAINT ck_metrics_value
    CHECK (value IS NOT NULL AND NOT is_nan(value) AND NOT is_infinite(value));
```

**Partitioning**: By month on `recorded_at`. See §16.

**Retention**: 
- Raw metrics: 90 days
- Rolled-up (hourly): 180 days
- Rolled-up (daily): 365 days
- Rollup data stored in separate `metrics_hourly` and `metrics_daily` aggregate tables

**Tenant Isolation**: Via `tenant_id` column. Null = global metric.

---

### 10.2 metrics_hourly / metrics_daily

**Schema**: `metrics_store` | **Purpose**: Pre-aggregated metrics for faster querying.

| Column | Type | Description |
|--------|------|-------------|
| `metric_name` | VARCHAR(255) | Metric identifier |
| `tenant_id` | UUID | Tenant (or null for global) |
| `tags` | JSONB | Dimension labels |
| `bucket` | TIMESTAMPTZ | Hourly/daily bucket start |
| `count` | BIGINT | Number of data points |
| `sum` | DOUBLE PRECISION | Sum of values |
| `min` | DOUBLE PRECISION | Minimum value |
| `max` | DOUBLE PRECISION | Maximum value |
| `avg` | DOUBLE PRECISION | Mean value |
| `p50` | DOUBLE PRECISION | 50th percentile |
| `p95` | DOUBLE PRECISION | 95th percentile |
| `p99` | DOUBLE PRECISION | 99th percentile |

Rolled up via cron job every hour (hourly) and every day (daily).

---

## 11. Audit Store

### 11.1 audit_log

**Schema**: `audit_store` | **Table**: `audit_log` | **Purpose**: Immutable audit trail for security, compliance, and debugging.

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| `id` | UUID | PK | `gen_random_uuid()` | — |
| `tenant_id` | UUID | NOT NULL | — | Tenant context |
| `user_id` | VARCHAR(255) | — | NULL | Acting user (NULL for system actions) |
| `action` | VARCHAR(100) | NOT NULL | — | `query_executed`, `schema_synced`, `config_changed`, `login`, `feedback_submitted`, `database_connected`, `team_invited`, etc. |
| `resource_type` | VARCHAR(100) | — | NULL | Type of resource affected |
| `resource_id` | VARCHAR(255) | — | NULL | ID of resource affected |
| `details` | JSONB | DEFAULT '{}' | `'{}'` | Action-specific details |
| `result` | VARCHAR(50) | NOT NULL | `'success'` | `success`, `failure`, `blocked` |
| `error_code` | VARCHAR(50) | — | NULL | If failure, the error code |
| `ip_address` | INET | — | NULL | Client IP |
| `user_agent` | TEXT | — | NULL | Client user-agent string |
| `request_id` | VARCHAR(100) | — | NULL | Correlating request ID |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | Event timestamp |

**Indexes**:
```sql
CREATE INDEX idx_audit_tenant_time ON audit_log(tenant_id, created_at DESC);
CREATE INDEX idx_audit_action ON audit_log(action);
CREATE INDEX idx_audit_user ON audit_log(user_id);
CREATE INDEX idx_audit_resource ON audit_log(resource_type, resource_id);
CREATE INDEX idx_audit_result ON audit_log(result);
CREATE INDEX idx_audit_request ON audit_log(request_id);
```

**Constraints**:
```sql
ALTER TABLE audit_log ADD CONSTRAINT ck_audit_result
    CHECK (result IN ('success', 'failure', 'blocked'));
```

**Partitioning**: By month on `created_at`.

**Retention**: 12 months (hot) → S3 archive (cold) for 3 years.

**Immutability**: UPDATE and DELETE are forbidden. Grant only INSERT and SELECT on this table.

```sql
-- Application user gets INSERT + SELECT only
REVOKE UPDATE, DELETE ON audit_log FROM opencode_app;
```

**Tenant Isolation**: Direct `tenant_id` column with RLS.

---

## 12. Job Queue Store

### 12.1 jobs

**Schema**: `job_queue` | **Table**: `jobs` | **Purpose**: Async job tracking for long-running operations (schema sync, data export).

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| `id` | UUID | PK | `gen_random_uuid()` | — |
| `tenant_id` | UUID | NOT NULL | — | Tenant context |
| `type` | VARCHAR(100) | NOT NULL | — | `schema_sync`, `data_export`, `bulk_feedback_process`, `tenant_provision` |
| `status` | VARCHAR(50) | NOT NULL | `'queued'` | `queued`, `running`, `completed`, `failed`, `cancelled` |
| `priority` | INTEGER | NOT NULL | 0 | Higher = more urgent |
| `params` | JSONB | DEFAULT '{}' | `'{}'` | Job-specific parameters |
| `result` | JSONB | DEFAULT '{}' | `'{}'` | Job completion result |
| `error_message` | TEXT | — | NULL | Failure detail |
| `progress` | REAL | NOT NULL | 0.0 | 0.0-1.0 progress indicator |
| `stage` | VARCHAR(100) | — | NULL | Current stage description |
| `max_retries` | INTEGER | NOT NULL | 3 | Maximum retry attempts |
| `retry_count` | INTEGER | NOT NULL | 0 | Current retry count |
| `scheduled_at` | TIMESTAMPTZ | — | NULL | Delayed execution (NULL = immediate) |
| `started_at` | TIMESTAMPTZ | — | NULL | Execution start time |
| `completed_at` | TIMESTAMPTZ | — | NULL | Completion/failure time |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | — |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | — |

**Indexes**:
```sql
CREATE INDEX idx_jobs_tenant ON jobs(tenant_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_type ON jobs(type);
-- Worker polling query
CREATE INDEX idx_jobs_poll ON jobs(status, priority DESC, scheduled_at, created_at)
    WHERE status = 'queued';
CREATE INDEX idx_jobs_scheduled ON jobs(scheduled_at) WHERE scheduled_at IS NOT NULL;
```

**Constraints**:
```sql
ALTER TABLE jobs ADD CONSTRAINT ck_jobs_status
    CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled'));
ALTER TABLE jobs ADD CONSTRAINT ck_jobs_progress
    CHECK (progress >= 0.0 AND progress <= 1.0);
ALTER TABLE jobs ADD CONSTRAINT ck_jobs_retry
    CHECK (retry_count <= max_retries);
```

**Partitioning**: By month on `created_at`. Completed/failed jobs move to `jobs_archive` after 30 days.

**Retention**: 
- Active jobs (queued/running): retained until completion
- Completed jobs: 30 days
- Failed jobs: 90 days
- After retention: moved to cold archive or deleted

**Tenant Isolation**: Direct `tenant_id` column with RLS.

---

## 13. Cache Store

### 13.1 Instance Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Version | Redis 7.2+ | Latest stable |
| Max memory | 10GB | Cache size limit |
| Eviction policy | `allkeys-lru` | LRU eviction for cache, noeviction for rate limit |
| Persistence | RDB every 5min | Quick restart, cache loss acceptable |
| TLS | Required | Encryption in transit |
| Connection | Cluster mode (3 nodes min) | High availability |

### 13.2 Database Separation

| DB | Purpose | Key Pattern | TTL | Eviction |
|----|---------|-------------|-----|----------|
| 0 | Query result cache | `cache:{tenant_id}:{query_hash}` | 5 min | allkeys-lru |
| 1 | Rate limit counters | `rl:{tenant_id}:{endpoint}:{period}` | Variable | allkeys-lru |
| 2 | Idempotency keys | `idem:{idempotency_key}` | 24h | allkeys-lru |
| 3 | User sessions | `sess:{session_token}` | JWT expiry + 5min | allkeys-lru |
| 4 | Lock keys | `lock:{resource_type}:{resource_id}` | 30s | noeviction |
| 5 | Job locks | `joblock:{job_type}` | 60s | noeviction |

### 13.3 Query Cache Schema

**Key**: `cache:{tenant_id}:{query_hash}`

**Value**:
```json
{
  "query_id": "qry_001",
  "sql": "SELECT ...",
  "results": [],
  "columns": [],
  "row_count": 42,
  "execution_ms": 2340,
  "cost": 0.0024,
  "cached_at": "2026-07-10T10:00:00Z",
  "ttl_seconds": 300
}
```

**Invalidation**: On schema sync (flush tenant cache), on feedback submission (flush specific query).

### 13.4 Rate Limit Schema

**Key**: `rl:{tenant_id}:{endpoint}:{window_start}`

**Value**: Counter (integer, incremented atomically via `INCR`)

**TTL**: Set on first increment to window duration (e.g., 60s for per-minute limits)

### 13.5 Idempotency Schema

**Key**: `idem:{idempotency_key}`

**Value**:
```json
{
  "response_status": 200,
  "response_body": {},
  "request_hash": "sha256_abc123",
  "created_at": "2026-07-10T10:00:00Z"
}
```

### 13.6 Session Schema

**Key**: `sess:{session_token}`

**Value**: User ID, tenant ID, role, expiry timestamp.

---

## 14. Vector Store

### 14.1 Collection Structure

**Collection name pattern**: `tenant_{tenant_id}_embeddings`

**One collection per tenant** for isolation. Created on tenant provisioning.

### 14.2 Collection Configuration

```json
{
  "collection_name": "tenant_tnt_001_embeddings",
  "vectors": {
    "size": 1024,
    "distance": "Cosine",
    "multivector_config": null
  },
  "sparse_vectors": {
    "splade": {
      "index": {
        "on_disk": true
      }
    }
  },
  "optimizers_config": {
    "default_segment_number": 6,
    "indexing_threshold": 10000,
    "memmap_threshold": 100000
  },
  "wal_config": {
    "wal_capacity_mb": 32
  },
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "always_ram": true
    }
  },
  "hnsw_config": {
    "m": 16,
    "ef_construct": 100,
    "full_scan_threshold": 10000,
    "max_indexing_threads": 2,
    "on_disk": false
  },
  "replication_factor": 2,
  "write_consistency_factor": 1,
  "on_disk_payload": true
}
```

### 14.3 Payload Schema

| Field | Type | Indexed | Description |
|-------|------|---------|-------------|
| `content_type` | Keyword | Yes | `schema_element`, `query`, `business_term`, `glossary` |
| `source_id` | Keyword | Yes | ID of source entity |
| `tenant_id` | Keyword | Yes | Tenant isolation |
| `text` | Text | No | Original text embedded |
| `source` | Keyword | Yes | `connector`, `annotator`, `learning_loop`, `manual` |
| `created_at` | Integer | Yes | Unix timestamp |
| `embedding_model` | Keyword | No | Model version used |

### 14.4 Payload Indexes (Qdrant)

```json
{
  "payload_schema": {
    "content_type": { "type": "keyword", "indexed": true },
    "source_id": { "type": "keyword", "indexed": true },
    "tenant_id": { "type": "keyword", "indexed": true },
    "source": { "type": "keyword", "indexed": true },
    "created_at": { "type": "integer", "indexed": true },
    "embedding_model": { "type": "keyword", "indexed": false }
  }
}
```

### 14.5 Collection Operations

| Operation | Frequency | Qdrant API |
|-----------|-----------|------------|
| Create collection | Per tenant (once) | `PUT /collections/{name}` |
| Upsert points | Schema sync, learning loop | `PUT /collections/{name}/points` |
| Search | Every query | `POST /collections/{name}/points/search` |
| Delete points | Schema change detected | `POST /collections/{name}/points/delete` |
| Delete collection | Tenant deletion | `DELETE /collections/{name}` |

### 14.6 Scaling

| Scale | Nodes | Replication | Shards |
|-------|-------|-------------|--------|
| Early (<100 tenants) | 1 | 2 | 4 |
| Growth (100-1K tenants) | 3 | 2 | 8 |
| Scale (1K-10K tenants) | 6 | 3 | 16 |

Each collection is small (~20K vectors per tenant). Total at 10K tenants: ~200M vectors. Qdrant handles this comfortably with the above node count.

---

## 15. Tenant Isolation Strategy

### 15.1 Isolation Matrix

| Table | Isolation Method | Column | Policy |
|-------|-----------------|--------|--------|
| tenants | None (global) | — | Admin access only |
| databases | RLS | tenant_id | `tenant_id = current_setting('app.tenant_id')::UUID` |
| schema_infos | RLS (inherited) | — | Via `JOIN databases ON schema_infos.database_id = databases.id` |
| tables | RLS (inherited) | — | Via `schema_infos → databases` |
| columns | RLS (inherited) | — | Via `tables → schema_infos → databases` |
| relationships | RLS | tenant_id | Direct |
| graph_nodes | RLS | tenant_id | Direct |
| graph_edges | RLS | tenant_id | Direct |
| query_history | RLS | tenant_id | Direct |
| feedback | RLS | tenant_id | Direct |
| config | RLS | tenant_id | scope_id = current tenant (or NULL) |
| metrics | Column tag | tenant_id | Application-level filter |
| audit_log | RLS | tenant_id | Direct |
| jobs | RLS | tenant_id | Direct |
| Qdrant vectors | Collection-per-tenant | — | Separate collection per tenant |

### 15.2 RLS Implementation (Standard Pattern)

```sql
-- Applied to all tenant-scoped tables
ALTER TABLE query_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON query_history
    AS PERMISSIVE
    FOR ALL
    TO opencode_app
    USING (tenant_id = current_setting('app.tenant_id')::UUID);
```

### 15.3 Session Setting

```sql
-- Called once per connection from KE API
SELECT set_config('app.tenant_id', $1, true);
```

The `set_config` third parameter `true` makes it local to the transaction. This ensures:
- No cross-tenant leakage via connection reuse
- Reset automatically on new transaction after pool checkout

### 15.4 Inherited RLS (for schema_store hierarchy)

```sql
-- schema_infos inherits via databases
CREATE POLICY tenant_isolation_inherited ON schema_infos
    AS PERMISSIVE
    FOR ALL
    TO opencode_app
    USING (
        EXISTS (
            SELECT 1 FROM databases
            WHERE databases.id = schema_infos.database_id
            AND databases.tenant_id = current_setting('app.tenant_id')::UUID
        )
    );
```

---

## 16. Partitioning Strategy

### 16.1 Partition Overview

| Table | Partition Key | Type | Interval | Retention | Auto-Manage |
|-------|--------------|------|----------|-----------|-------------|
| query_history | created_at | RANGE | Monthly | 12 months | Cron job |
| metrics | recorded_at | RANGE | Monthly | 6 months | Cron job |
| metrics_hourly | bucket | RANGE | Monthly | 12 months | Cron job |
| metrics_daily | bucket | RANGE | Yearly | 3 years | Cron job |
| audit_log | created_at | RANGE | Monthly | 12 months | Cron job |
| feedback | created_at | RANGE | Monthly | Permanent | Cron job |
| jobs | created_at | RANGE | Monthly | Archive + 3mo | Cron job |
| graph_nodes | tenant_id | HASH (mod 16) | — | — | Manual (when >50M) |
| graph_edges | tenant_id | HASH (mod 16) | — | — | Manual (when >50M) |

### 16.2 Partition Template: Monthly RANGE

```sql
-- Master table
CREATE TABLE query_history (
    id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    -- ... other columns
) PARTITION BY RANGE (created_at);

-- Monthly partitions
CREATE TABLE query_history_y2026m06 PARTITION OF query_history
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE query_history_y2026m07 PARTITION OF query_history
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE query_history_y2026m08 PARTITION OF query_history
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');

-- Indexes on each partition (automatically inherited, or create per partition)
CREATE INDEX idx_qh_tenant_created_y2026m07
    ON query_history_y2026m07(tenant_id, created_at DESC);
```

### 16.3 Partition Management (Cron Job)

```python
# Run daily via cron
def manage_partitions():
    # Create partitions 3 months ahead
    for month in next_3_months():
        if not partition_exists(month):
            create_partition('query_history', month)
    
    # Drop partitions beyond retention
    for partition in outdated_partitions('query_history', retention_months=12):
        drop_partition(partition)
```

### 16.4 Hash Partition Template (for graph_store)

```sql
CREATE TABLE graph_nodes (
    id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    -- ...
) PARTITION BY HASH (tenant_id);

-- 16 partitions
CREATE TABLE graph_nodes_p0 PARTITION OF graph_nodes FOR VALUES WITH (MODULUS 16, REMAINDER 0);
CREATE TABLE graph_nodes_p1 PARTITION OF graph_nodes FOR VALUES WITH (MODULUS 16, REMAINDER 1);
-- ... through p15
```

---

## 17. Backup & Recovery Strategy

### 17.1 Backup Schedule

| Data | Method | Frequency | Retention | RPO | RTO |
|------|--------|-----------|-----------|-----|-----|
| PostgreSQL (full) | pg_dump (custom format) | Daily | 30 days | 24h | 2h |
| PostgreSQL (WAL) | WAL archiving | Continuous | 7 days | 5min | 1h (PITR) |
| Qdrant (snapshot) | Qdrant API snapshot | Daily | 7 days | 24h | 2h |
| Redis (RDB) | RDB snapshot | Every 5min | 1 day | 5min | 5min |
| Application config | Git (versioned) | Per commit | Permanent | N/A | 30min |

### 17.2 Recovery Procedures

| Scenario | Recovery Method | Steps |
|----------|----------------|-------|
| Single row corruption | Point-in-time recovery from WAL | Restore to timestamp before corruption, extract row |
| Table corruption | pg_restore single table | Restore table from latest dump |
| Full database loss | PITR + WAL | Restore base backup, replay WAL to latest |
| Qdrant data loss | Qdrant snapshot restore | Restore snapshot, index rebuild |
| Region failure | Cross-region replica | Promote replica, update DNS |

### 17.3 Backup Storage

| Environment | Storage | Encryption |
|-------------|---------|------------|
| Dev | Local disk | — |
| Staging | S3 (same region) | AES-256 |
| Production | S3 (cross-region) | AES-256 + KMS |
| On-prem | NFS + remote copy | GPG |

---

## 18. Retention Policies

| Table | Hot (PostgreSQL) | Warm (Archive) | Cold (S3) | Total |
|-------|-----------------|----------------|-----------|-------|
| tenants | Permanent | — | — | Permanent |
| databases | Permanent | — | — | Permanent |
| schema_infos | Permanent | — | — | Permanent |
| tables | Permanent | — | — | Permanent |
| columns | Permanent | — | — | Permanent |
| relationships | Permanent | — | — | Permanent |
| graph_nodes | Permanent | — | — | Permanent |
| graph_edges | Permanent | — | — | Permanent |
| query_history | 12 months | — | 3 years | 4 years |
| feedback | Permanent | — | — | Permanent |
| config | Permanent | — | — | Permanent |
| metrics (raw) | 90 days | 180 days (hourly) | 365 days (daily) | 1 year |
| audit_log | 12 months | S3 archive | 3 years | 4 years |
| jobs (completed) | 30 days | — | — | 30 days |
| jobs (failed) | 90 days | — | — | 90 days |
| Qdrant vectors | Permanent | — | — | Permanent |

---

## 19. Scaling Strategy

### 19.1 Current Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  PostgreSQL   │     │    Redis      │     │   Qdrant     │
│  (1 primary + │     │  (3-node      │     │  (3-node     │
│   2 replicas) │     │   cluster)    │     │   cluster)   │
└──────────────┘     └──────────────┘     └──────────────┘
```

### 19.2 Scale-Up Path

| Stage | Tenants | PostgreSQL | Redis | Qdrant | Notes |
|-------|---------|------------|-------|--------|-------|
| 1 | < 100 | db.r6g.large (2 vCPU, 16GB) | cache.r6g.large | 1 node | Single AZ |
| 2 | 100-500 | db.r6g.xlarge (4 vCPU, 32GB) | cache.r6g.xlarge | 3 nodes | Multi-AZ replicas |
| 3 | 500-2K | db.r6g.2xlarge (8 vCPU, 64GB) | cache.r6g.2xlarge | 6 nodes | Read replicas for analytics |
| 4 | 2K-5K | db.r6g.4xlarge (16 vCPU, 128GB) | cache.r6g.4xlarge | 6 nodes | Connection pooling tuning |
| 5 | 5K-10K | Citus/read replicas (horizontal) | Cluster sharding | 12 nodes | Shard PostgreSQL by tenant_id |

### 19.3 Read Replica Strategy

| Replica Purpose | Tables | Query Types | Lag Tolerance |
|-----------------|--------|-------------|---------------|
| API read path | query_history, schema_store | SELECT by ID | 100ms |
| Analytics | query_history, metrics, audit | Aggregation queries | 1s |
| Learning loop | query_history, feedback | Batch processing | 5s |
| Backups | Full database | pg_dump | — |

### 19.4 Connection Pooling (PgBouncer)

| Pool | Services | Pool Size | Target |
|------|----------|-----------|--------|
| ke_pool | KE API | 50 | Low latency store reads |
| pipeline_pool | Query pipeline | 20 | Target DB connections |
| learning_pool | Learning loop | 10 | Batch processing |
| admin_pool | Admin dashboard | 5 | Reporting queries |

---

## 20. Migration Strategy

### 20.1 Tooling

- **Tool**: Alembic (async support via `alembic-postgresql-enum` or raw SQL in migration functions)
- **Location**: `/backend/ke/migrations/`
- **Naming**: `{version}_{description}.py` (e.g., `0002_create_graph_store.py`)
- **Config**: `alembic.ini` at `/backend/ke/`

### 20.2 Migration Rules

| Rule | Rationale |
|------|-----------|
| One migration per logical change | Clean version history |
| Always provide `upgrade()` and `downgrade()` | Rollback support |
| Backward-compatible changes only in minor versions | No breaking changes without major version |
| Data migrations in separate files from schema migrations | Isolation of concerns |
| Large table migrations use batch processing | Prevent table locks |
| Test migration on staging before production | Validation |
| Run `downgrade()` test in CI | Ensure rollback works |

### 20.3 Migration Types

| Type | File Suffix | Writable During Migrate? | Rollback? |
|------|-------------|-------------------------|-----------|
| Schema change | `*_schema.py` | No (lock) | Yes |
| Data migration | `*_data.py` | Yes (no lock) | Yes (with reverse data) |
| Index creation | `*_index.py` | Yes (CONCURRENTLY) | Yes |
| Reference data seed | `*_seed.py` | Yes | Yes |

### 20.4 Zero-Downtime Migration Process

```python
# Example: Adding a NOT NULL column with default
# Step 1: Add column as nullable
op.add_column('query_history', sa.Column('tokens_in', sa.Integer(), nullable=True))

# Step 2: Backfill data (batch, in separate migration + app code)
# Run in background: UPDATE query_history SET tokens_in = 0 WHERE tokens_in IS NULL LIMIT 10000;

# Step 3: Add NOT NULL constraint
op.alter_column('query_history', 'tokens_in', nullable=False)
```

---

## 21. Soft Delete Strategy

### 21.1 Soft-Deleted Tables

| Table | Soft Delete Column | Hard Delete After | Hard Delete Method |
|-------|-------------------|-------------------|--------------------|
| tenants | `deleted_at` | 30 days | Cron job |
| databases | `deleted_at` | 7 days | Cron job (cascades) |
| query_history | — (hard delete) | 12 months | Partition drop |
| feedback | — (no delete) | Permanent | — |

### 21.2 Soft Delete Pattern

```sql
-- Add deleted_at column (NULL = not deleted)
ALTER TABLE tenants ADD COLUMN deleted_at TIMESTAMPTZ;

-- Create partial unique index (prevents slug collision on re-registration)
CREATE UNIQUE INDEX uq_tenants_slug ON tenants(slug) WHERE deleted_at IS NULL;

-- Queries filter automatically
SELECT * FROM tenants WHERE deleted_at IS NULL;
```

### 21.3 Hard Delete Cron

```sql
-- Hard delete tenants soft-deleted > 30 days ago
DELETE FROM tenants WHERE deleted_at IS NOT NULL
    AND deleted_at < NOW() - INTERVAL '30 days';
```

### 21.4 Cascade Behavior

When a tenant is hard deleted:
1. `databases` rows CASCADE DELETE
2. `schema_infos` CASCADE from databases
3. `tables` CASCADE from schema_infos
4. `columns` CASCADE from tables
5. `query_history` CASCADE (retention already handled by partition dropping)
6. `feedback` CASCADE
7. `graph_nodes` CASCADE
8. `graph_edges` CASCADE
9. `audit_log` CASCADE
10. Qdrant collection deleted via application code

---

## 22. Future Evolution

### 22.1 Year 1 (Current)

- Single PostgreSQL + PgBouncer
- All tables in single database

### 22.2 Year 2

| Change | Driver | Impact |
|--------|--------|--------|
| Read replicas for analytics | Analytics queries impacting API latency | New connection pool for read replicas |
| Metrics to separate time-series DB (TimescaleDB) | Metrics volume > 1B rows/month | New connection, migration from pg partitions |

### 22.3 Year 3

| Change | Driver | Impact |
|--------|--------|--------|
| History store to separate PG instance | History > 5B rows | Application-level routing |
| Graph store migration to dedicated graph DB | Recursive CTE performance | Only if CTE traversal > 500ms P95 |
| PostgreSQL read replicas | Cache > 50GB | Application-level routing |
| Database-per-tenant for Enterprise | Strict isolation requirement | Connection pooling per tenant, new provisioning flow |

### 22.4 Year 4+

| Change | Driver | Impact |
|--------|--------|--------|
| Global data mesh with cross-tenant analytics | Enterprise feature | New catalog service, query federation |
| Real-time schema change streaming | CDC requirement | Debezium, Kafka integration |
| Multi-region active-active | Latency requirement | CRDT-based replication, conflict resolution |
