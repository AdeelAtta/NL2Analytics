# Knowledge Engine Specification

**Version**: 1.0.0 | **Status**: Approved | **Last Updated**: 2026-07-10

**Document Owner**: Enterprise Knowledge Architect

**Cross-References**:
- [Database-Specification.md](Database-Specification.md) — KE store implementations (PostgreSQL, Qdrant)
- [API-Specification.md](API-Specification.md) — KE API endpoint contracts
- [AI-Agent-Specification.md](AI-Agent-Specification.md) — Retriever, Planner, Learning agent KE usage
- [Planner-Specification.md](Planner-Specification.md) — Knowledge graph query patterns
- [Retriever-Specification.md](Retriever-Specification.md) — Context retrieval pipeline
- [Schema-Specification.md](Schema-Specification.md) — Schema store model, table/column representation
- [ModelRouter-Specification.md](ModelRouter-Specification.md) — Model capability profiles stored in KE
- [Performance-Budgets.md](Performance-Budgets.md) — KE API latency budgets

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Metadata Extraction](#2-metadata-extraction)
3. [Schema Intelligence](#3-schema-intelligence)
4. [Business Ontology](#4-business-ontology)
5. [Knowledge Graph](#5-knowledge-graph)
6. [Semantic Layer](#6-semantic-layer)
7. [Context Layer](#7-context-layer)
8. [Embedding Pipeline](#8-embedding-pipeline)
9. [Retriever](#9-retriever)
10. [Learning Engine](#10-learning-engine)
11. [Versioning](#11-versioning)
12. [Context APIs](#12-context-apis)
13. [Store Interface Reference](#13-store-interface-reference)
14. [Cross-Cutting Concerns](#14-cross-cutting-concerns)

---

## 1. Architecture Overview

### 1.1 Why the Knowledge Engine Is the Architectural Core

The Knowledge Engine (KE) is the architectural core of the Enterprise Data Intelligence Platform. **Every component is a consumer or producer of the Knowledge Engine.** No component holds authoritative state. This decision was made because:

1. **Loose coupling**: Components can be added, removed, or replaced without restructuring. Adding proactive insights in Year 3 is adding a new KE consumer, not rewriting the pipeline.
2. **Single source of truth**: All schema knowledge, business context, query history, and learned patterns live in one system. No data duplication, no sync issues between components.
3. **Observability by design**: Since all data flows through the KE API, we can instrument, audit, and debug every operation that touches knowledge.
4. **Incremental learning**: The Learning Engine enriches the KE over time. Every component automatically benefits from improved knowledge without code changes.

### 1.2 Logical Architecture

```
                                    ┌───────────────────┐
                                    │  External Systems  │
                                    │  (Target DBs, LLM) │
                                    └─────────┬─────────┘
                                              │
                    ┌─────────────────────────────────────────┐
                    │            ┌───────────────┐             │
                    │  ┌────────▶│ Schema Intel  │◀────────┐  │
                    │  │         │ (producer)    │          │  │
                    │  │         └───────────────┘          │  │
                    │  │                                    │  │
                    │  │  ┌───────────────┐                 │  │
                    │  ├──▶│  Ontology     │                 │  │
                    │  │   │  Builder     │                 │  │
                    │  │   │  (producer)  │                 │  │
    ┌──────────────┐│  │   └───────────────┘                 │  │
    │ Query        ││  │                                     │  │
    │ Pipeline     ││  │  ┌───────────────┐                 │  │
    │ (consumer +  ││  ├──▶│  Learning     │                 │  │
    │  producer)   ││  │   │  Engine      │                 │  │
    └──────────────┘│  │   │  (producer)  │                 │  │
                    │  │   └───────────────┘                 │  │
                    │  │                                     │  │
                    │  │            ┌───────────┐            │  │
                    │  └────────────│ KE API    │────────────┘  │
                    │               │ (port 8200)│              │
                    │               └─────┬─────┘              │
                    │                     │                    │
                    │         ┌───────────┼───────────┐        │
                    │         │           │           │        │
                    │         ▼           ▼           ▼        │
                    │  ┌──────────┐ ┌──────────┐ ┌──────────┐ │
                    │  │  Stores  │ │  Events  │ │  Cache   │ │
                    │  │ (PG+Qd)  │ │  (Redis) │ │  (Redis) │ │
                    │  └──────────┘ └──────────┘ └──────────┘ │
                    └─────────────────────────────────────────┘
```

### 1.3 Store Ownership Map

```
┌──────────────────────────────────────────────────────────────────┐
│                     Knowledge Engine (KE)                         │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐│
│  │ Schema Store │  │  Vector Index│  │      Graph Store         ││
│  │ (PostgreSQL) │  │  (Qdrant)    │  │  (PostgreSQL CTEs)       ││
│  ├──────────────┤  ├──────────────┤  ├──────────────────────────┤│
│  │ Raw schemas  │  │ Embeddings   │  │ Business ontology nodes  ││
│  │ Tables       │  │ Dense+sparse │  │ Relationships/edges      ││
│  │ Columns      │  │ Schema elem  │  │ Query patterns           ││
│  │ FKs/Rels     │  │ Queries      │  │ Domain hierarchies       ││
│  │ Descriptions │  │ Business terms│ │ Glossary terms           ││
│  └──────────────┘  └──────────────┘  └──────────────────────────┘│
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐│
│  │ History Store│  │ Feedback     │  │     Config Store          ││
│  │ (PostgreSQL) │  │ Store (PG)   │  │     (PostgreSQL)          ││
│  ├──────────────┤  ├──────────────┤  ├──────────────────────────┤│
│  │ Query logs   │  │ User ratings │  │ Tenant settings          ││
│  │ Execution    │  │ Corrections  │  │ Model config              ││
│  │ Costs        │  │ Quality      │  │ Feature flags             ││
│  │ Latency data │  │ scores       │  │ User preferences          ││
│  └──────────────┘  └──────────────┘  └──────────────────────────┘│
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐                               │
│  │ Metrics Store│  │  Audit Store │                               │
│  │ (PostgreSQL) │  │  (PostgreSQL)│                               │
│  ├──────────────┤  ├──────────────┤                               │
│  │ KPIs         │  │ Immutable    │                               │
│  │ Counters     │  │ action log   │                               │
│  │ Aggregations │  │ Compliance   │                               │
│  │ Rollups      │  │ trail        │                               │
│  └──────────────┘  └──────────────┘                               │
└──────────────────────────────────────────────────────────────────┘
```

### 1.4 Data Flow: Full Pipeline

```
Metadata Extraction ──▶ Schema Intelligence ──▶ Embedding Pipeline
       │                       │                       │
       │                       ▼                       │
       │           ┌─────────────────────┐             │
       └──────────▶│   Business Ontology  │◀────────────┘
                   └─────────┬───────────┘
                             │
                             ▼
                    ┌─────────────────────┐
                    │   Knowledge Graph    │
                    └─────────┬───────────┘
                              │
                              ▼
                     ┌─────────────────────┐
                     │    Semantic Layer    │
                     └─────────┬───────────┘
                               │
                               ▼
                      ┌─────────────────────┐
                      │    Context Layer     │
                      │   (Retriever API)   │
                      └─────────┬───────────┘
                                │
                                ▼
                       ┌─────────────────────┐
                       │  Query Pipeline     │
                       │  (consumes context) │
                       └─────────┬───────────┘
                                 │ (results + feedback)
                                 ▼
                       ┌─────────────────────┐
                       │   Learning Engine    │
                       │  (closes the loop)  │
                       └─────────────────────┘
```

### 1.5 Design Rationale Summary

| Decision | Rationale |
|----------|-----------|
| KE API as single internal interface | ADR-004: No component talks to another directly. Enforces loose coupling. Makes stores swappable. |
| All state in KE, components stateless | ADR-003: Components can be killed and restarted without data loss. Horizontal scaling is trivial. |
| Self-hosted PostgreSQL + Qdrant | ADR-005: Same architecture in all 5 deployment modes (cloud, VPC, on-prem, air-gapped). No external API dependencies. |
| RLS + collection-per-tenant isolation | ADR-006: Shared infrastructure for multi-tenancy without cross-tenant leakage. Scales to 10K tenants without per-tenant databases. |
| No dedicated graph DB (recursive CTEs) | ADR-002 (implicit): Graph queries in MVP are depth-limited (max 5). PostgreSQL recursive CTEs handle this efficiently. Adding Neo4j in Year 2 if CTE latency exceeds 500ms. |
| Batch-only learning loop | Online learning risks bad feedback immediately degrading accuracy. 5-minute batch cycles provide a validation + quality gate before any KE update. |
| BGE-M3 for embeddings | Open source, 1024-dim, supports dense + sparse (SPLADE) in one model. No API costs. Self-hostable on same GPU infrastructure. |

---

## 2. Metadata Extraction

### 2.1 Overview

Metadata Extraction is the entry point for all knowledge about a tenant's databases. It connects to target databases, introspects their schemas, and produces a normalized representation of tables, columns, types, constraints, and relationships.

### 2.2 Responsibilities

1. Connect to target databases using pluggable connectors
2. Extract full schema metadata (schemas, tables, columns, types, defaults, constraints)
3. Extract explicit foreign key relationships
4. Normalize all metadata into a unified representation
5. Detect schema changes (DDL diffs) between syncs
6. Handle connection failures, permission errors, timeouts gracefully
7. Report extraction progress and metrics

### 2.3 Why Metadata Extraction Is Separate from Schema Intelligence

Metadata Extraction is **schema discovery** (what exists). Schema Intelligence (next section) is **semantic enrichment** (what it means). They are separated because:

1. Extraction is connector-specific; enrichment is LLM-specific. Changes to connectors don't affect enrichment prompts.
2. Extraction runs on every sync; enrichment runs only when descriptions are stale or missing.
3. Extraction must work offline (air-gapped); enrichment requires LLM access.
4. Different failure modes: extraction fails due to network/auth; enrichment fails due to LLM errors.

### 2.4 Inputs

```json
{
  "database_id": "db_001",
  "tenant_id": "tnt_001",
  "connector_config": {
    "db_type": "postgresql",
    "host": "prod-db.internal",
    "port": 5432,
    "database": "main",
    "username": "opencode_user",
    "password": "********",
    "ssl": true,
    "schema_filter": ["public", "sales"]
  },
  "options": {
    "include_views": false,
    "include_indexes": false,
    "timeout_seconds": 30,
    "extract_sample_rows": false
  }
}
```

### 2.5 Outputs

```json
{
  "database_name": "Production",
  "db_type": "postgresql",
  "extracted_at": "2026-07-10T10:00:00Z",
  "schemas": [
    {
      "name": "public",
      "tables": [
        {
          "name": "customers",
          "ddl": "CREATE TABLE customers (id UUID PRIMARY KEY, name VARCHAR(255) NOT NULL, ...)",
          "columns": [
            {
              "name": "id",
              "ordinal_position": 1,
              "data_type": "uuid",
              "is_nullable": false,
              "is_primary_key": true,
              "default_value": "gen_random_uuid()",
              "comment": null,
              "character_maximum_length": null,
              "numeric_precision": null,
              "numeric_scale": null,
              "foreign_key_table": null,
              "foreign_key_column": null
            }
          ],
          "row_count_estimate": 50000
        }
      ]
    }
  ],
  "relationships": [
    {
      "source_table": "orders",
      "source_column": "customer_id",
      "target_table": "customers",
      "target_column": "id",
      "constraint_name": "fk_orders_customer",
      "constraint_type": "foreign_key"
    }
  ],
  "statistics": {
    "schema_count": 2,
    "table_count": 142,
    "column_count": 2840,
    "relationship_count": 85,
    "extraction_duration_ms": 12340
  }
}
```

**Error output**:
```json
{
  "error": true,
  "code": "CONNECTION_FAILED",
  "message": "Could not connect to database at prod-db.internal:5432",
  "details": {
    "attempted_host": "prod-db.internal",
    "attempted_port": 5432,
    "error_type": "connection_timeout",
    "error_detail": "Connection timed out after 30 seconds"
  }
}
```

### 2.6 Storage

| Data | Target Store | Table/Collection |
|------|-------------|------------------|
| Database connection metadata | Schema Store | `databases` |
| Schema/table/column definitions | Schema Store | `schema_infos`, `tables`, `columns` |
| Foreign key relationships | Schema Store | `relationships` |
| Raw DDL | Schema Store | `tables.ddl`, `schema_infos.raw_ddl` |

### 2.7 Algorithms

#### Connector Interface (Abstract Base)

```python
class BaseConnector(ABC):
    """Every DB type implements this interface."""

    @abstractmethod
    async def connect(self, config: ConnectorConfig) -> None:
        """Establish connection to target database."""
        pass

    @abstractmethod
    async def extract_schemas(self) -> list[SchemaInfo]:
        """List all schemas in the database."""
        pass

    @abstractmethod
    async def extract_tables(self, schema_name: str) -> list[TableInfo]:
        """List all tables in a schema with metadata."""
        pass

    @abstractmethod
    async def extract_columns(self, schema_name: str, table_name: str) -> list[ColumnInfo]:
        """List all columns in a table with types and constraints."""
        pass

    @abstractmethod
    async def extract_relationships(self) -> list[RelationshipInfo]:
        """Extract foreign key constraints and relationships."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close connection."""
        pass
```

**Why abstract base class?** Each database type has different introspection queries. The abstraction lets us add connectors without modifying any pipeline code. The Connector Registry pattern (dict of type → class) enables plug-and-play.

#### PostgreSQL Connector Algorithm

```
1. Connect using asyncpg with TLS
2. Extract schemas:
   SELECT schema_name FROM information_schema.schemata
   WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
3. For each schema, extract tables:
   SELECT table_name, table_type, pg_size_pretty(...)
   FROM information_schema.tables WHERE table_schema = $1
4. For each table, extract columns:
   SELECT column_name, ordinal_position, data_type, is_nullable,
          column_default, character_maximum_length, ...
   FROM information_schema.columns WHERE table_schema = $1 AND table_name = $2
5. Extract primary keys:
   SELECT kcu.column_name FROM information_schema.table_constraints tc
   JOIN information_schema.key_column_usage kcu ON ...
   WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = $1
6. Extract foreign keys:
   SELECT ... FROM information_schema.table_constraints tc
   JOIN information_schema.constraint_column_usage ccu ON ...
   WHERE tc.constraint_type = 'FOREIGN KEY'
7. Extract row estimates:
   SELECT reltuples::bigint FROM pg_class WHERE relname = $1
```

**Why raw SQL over SQLAlchemy introspection?** SQLAlchemy's `inspector` API doesn't expose all metadata uniformly across dialects (e.g., comments, extended types, partition info). Raw information_schema queries are more complete and faster for batch extraction.

### 2.8 Interfaces

```python
class MetadataExtractor:
    """Orchestrates metadata extraction for a single database."""

    async def extract(self, db_id: UUID, config: ConnectorConfig) -> ExtractionResult:
        """Full extraction pipeline."""
        pass

    async def extract_incremental(self, db_id: UUID, since: datetime) -> ExtractionResult:
        """Extract only changed schemas since given timestamp."""
        pass

    async def test_connection(self, config: ConnectorConfig) -> ConnectionTestResult:
        """Test connectivity without full extraction."""
        pass
```

```python
class ConnectorRegistry:
    """Registry of available database connectors."""

    @classmethod
    def register(cls, db_type: str, connector_cls: type[BaseConnector]) -> None: ...

    @classmethod
    def get_connector(cls, db_type: str) -> type[BaseConnector]: ...
```

### 2.9 Failure Handling

| Failure Mode | Detection | Recovery |
|-------------|-----------|----------|
| Connection timeout | asyncpg timeout (30s default) | Retry 3x (5s, 15s, 30s backoff). If all fail → ERR-009 |
| Authentication failure | asyncpg InvalidAuthorizationSpecification | No retry. Set sync_status='error', store error. Notify user. |
| Permission denied (no information_schema access) | Query permission error | Return partial results (available schemas only). Flag as degraded sync. |
| Schema-level permission (can't see some tables) | Per-table error | Skip table, continue sync. Flag in sync results. |
| Database unreachable (network error) | Connection refused/DNS failure | Retry 3x. If all fail → ERR-009. |
| Query timeout during extraction | Statement timeout (30s per query) | Retry query once with extended timeout. |
| Partial failure (one schema fails, others succeed) | Per-schema try/catch | Report partial success. Include error details for failed schemas. |

### 2.10 Metrics

| Metric | Type | Description | Target |
|--------|------|-------------|--------|
| `extraction.duration_ms` | Histogram | Total sync duration | P95 < 30s (200 tables) |
| `extraction.tables_per_second` | Gauge | Extraction throughput | > 50 tables/s |
| `extraction.success_rate` | Counter | Success/failure ratio | > 99% |
| `extraction.connector.errors` | Counter | Per-connector error count | 0 |
| `extraction.schema_count` | Gauge | Schemas extracted | Per tenant |
| `extraction.table_count` | Gauge | Tables extracted | Per tenant |
| `extraction.relationship_count` | Gauge | Relationships found | Per tenant |

### 2.11 Scaling

| Dimension | Strategy |
|-----------|----------|
| Per-tenant syncs | Each tenant syncs independently. Parallel syncs for different tenants. |
| Large schemas (1000+ tables) | Connector parallelizes per-schema extraction. Multiple concurrent queries against target DB. |
| Connection limits | Each connector uses a separate connection pool (min 2, max 5 connections per target DB). |
| Sync scheduling | Poisson process: stagger syncs across tenants to avoid thundering herd. |

### 2.12 Testing

| Test Type | What It Tests | How |
|-----------|--------------|-----|
| Unit | Connector interface contract | Mock connector implementing interface, verify all methods called |
| Unit | Schema normalization | Known input → expected output fixtures |
| Integration | PostgreSQL connector | Real PostgreSQL container (testcontainers) |
| Integration | Change detection | Two snapshots, compare diffs |
| Integration | Error handling | Network failure simulation, auth failure simulation |
| E2E | Full extraction pipeline | Real PG → KE API → stores populated |

### 2.13 Dependencies

| Dependency | Reason |
|-----------|--------|
| asyncpg | Async PostgreSQL driver |
| SQLAlchemy 2.0 | Schema type mapping and SQL generation |
| pymysql / snowflake-connector / google-cloud-bigquery / duckdb | DB-specific drivers |
| KE API client | Writing extracted data to stores |
| Policy enforcement layer | Schema extraction runs through RBAC checks |

### 2.14 Sequence Diagram

```
Orchestrator     Connector        Target DB        KE API Store       Embedding
    │               │               │                  │                  │
    │ extract()     │               │                  │                  │
    │──────────────>│               │                  │                  │
    │               │ connect()     │                  │                  │
    │               │──────────────>│                  │                  │
    │               │  connected    │                  │                  │
    │               │<──────────────│                  │                  │
    │               │               │                  │                  │
    │               │ get_schemas() │                  │                  │
    │               │──────────────>│                  │                  │
    │               │  schemas      │                  │                  │
    │               │<──────────────│                  │                  │
    │               │               │                  │                  │
    │               │ for each schema:                │                  │
    │               │ get_tables()  │                  │                  │
    │               │──────────────>│                  │                  │
    │               │  tables       │                  │                  │
    │               │<──────────────│                  │                  │
    │               │               │                  │                  │
    │               │ for each table:                 │                  │
    │               │ get_columns() │                  │                  │
    │               │──────────────>│                  │                  │
    │               │  columns      │                  │                  │
    │               │<──────────────│                  │                  │
    │               │               │                  │                  │
    │               │ get_relationships()             │                  │
    │               │──────────────>│                  │                  │
    │               │  relationships │                 │                  │
    │               │<──────────────│                  │                  │
    │               │               │                  │                  │
    │               │ close()       │                  │                  │
    │               │──────────────>│                  │                  │
    │               │               │                  │                  │
    │ result        │               │                  │                  │
    │<──────────────│               │                  │                  │
    │               │               │                  │                  │
    │ store to KE   │               │                  │                  │
    │────────────────────────────────────────────────>│                  │
    │               │               │                  │                  │
    │ trigger       │               │                  │                  │
    │ enrichment    │               │                  │                  │
    │─────────────────────────────────────────────────>│(see Schema Intel)│
```

---

## 3. Schema Intelligence

### 3.1 Overview

Schema Intelligence enriches raw metadata with semantic understanding. It takes the normalized schema from Metadata Extraction and produces human-readable descriptions, inferred relationships, and domain classifications. This is where "customers.id" becomes "the primary key for customer master data."

### 3.2 Responsibilities

1. Generate business descriptions for tables and columns using LLMs
2. Infer relationships that aren't explicit foreign keys (naming heuristics, join pattern analysis)
3. Classify tables into business domains (sales, finance, HR, inventory)
4. Detect column semantics (PII, currency, date, identifier, metric, dimension)
5. Generate schema summaries and table-level documentation
6. Update descriptions when schema changes (version-aware enrichment)
7. Flag ambiguous or low-confidence descriptions for human review

### 3.3 Why LLM-Based Enrichment

**Alternatives considered and rejected**:
- **Rule-based naming** (e.g., "strip underscores, capitalize"): Produces "Customer Name" from "customer_name" but misses business context. Can't distinguish "revenue" vs "amount" vs "total."
- **Dictionary lookup** (common column name → description): Fragile, doesn't scale to diverse enterprise schemas.
- **Human-written descriptions**: Won't scale. Enterprise customers have 100-5,000 tables. We can't ask them to describe every column.

**Why LLMs work here**: Column/table description generation is a **constrained generation** task — the LLM receives the table's columns, types, FKs, and optionally neighbor tables. The output is a short description. This is well within current LLM capabilities. The prompt template provides guardrails against hallucination.

### 3.4 Inputs

```json
{
  "schema_id": "sch_001",
  "tables": [
    {
      "name": "customers",
      "columns": [
        {"name": "id", "type": "uuid", "is_pk": true, "fk_ref": null},
        {"name": "name", "type": "varchar(255)", "is_pk": false, "fk_ref": null},
        {"name": "email", "type": "varchar(255)", "is_pk": false, "fk_ref": null},
        {"name": "created_at", "type": "timestamptz", "is_pk": false, "fk_ref": null}
      ],
      "row_count_estimate": 50000,
      "foreign_keys": [
        {"column": "id", "ref_table": "orders", "ref_column": "customer_id"}
      ]
    }
  ]
}
```

### 3.5 Outputs

```json
{
  "schema_id": "sch_001",
  "tables": [
    {
      "name": "customers",
      "description": "Customer master data containing contact information, account details, and registration timestamps for all active customers. Each row represents a unique customer account.",
      "business_domain": "sales",
      "columns": [
        {
          "name": "id",
          "description": "Primary key for the customer table. Auto-generated UUID. Referenced by orders.customer_id.",
          "semantic_type": "identifier",
          "pii": false,
          "confidence": 0.95
        },
        {
          "name": "name",
          "description": "Full legal name of the customer company or individual.",
          "semantic_type": "name",
          "pii": true,
          "confidence": 0.90
        },
        {
          "name": "email",
          "description": "Primary email address for account communications and login.",
          "semantic_type": "contact",
          "pii": true,
          "confidence": 0.95
        },
        {
          "name": "created_at",
          "description": "Timestamp when the customer account was created. Timezone-aware.",
          "semantic_type": "timestamp",
          "pii": false,
          "confidence": 0.98
        }
      ],
      "inferred_relationships": [
        {
          "source_column": "id",
          "target_table": "orders",
          "target_column": "customer_id",
          "type": "inferred",
          "confidence": 0.95,
          "rationale": "Naming convention: customers.id is referenced by orders.customer_id. Column name contains parent table name as prefix."
        }
      ],
      "summary": "Central customer table with 50K rows. Core entity for sales domain. Primary relationship is to orders via customer_id."
    }
  ],
  "metadata": {
    "model_used": "qwen2.5-72b",
    "enrichment_duration_ms": 28500,
    "tables_enriched": 25,
    "columns_enriched": 350,
    "relationships_inferred": 18
  }
}
```

### 3.6 Storage

| Data | Target Store | Table/Collection | Update Strategy |
|------|-------------|------------------|-----------------|
| Table descriptions | Schema Store | `tables.description` | Upsert on enrichment |
| Column descriptions | Schema Store | `columns.description` | Upsert on enrichment |
| Column semantic types | Schema Store | `columns.properties` (JSONB extension) | Upsert on enrichment |
| Business domain | Schema Store | `tables.properties->>'domain'` | Upsert on enrichment |
| Inferred relationships | Schema Store | `relationships` (type='inferred') | Upsert, deduplicated with FK rels |
| Enrichment metadata | Metrics Store | `metrics` | Append-only |

### 3.7 Algorithms

#### Description Generation Prompt

**Why this prompt design?** Enterprise schemas have poor naming. The LLM needs maximum context: column names, data types, constraints, neighboring tables, and sampled values. The `*UNKNOWN*` convention forces the LLM to say "I don't know" rather than hallucinate.

```
System: You are a database documentation expert. Your task is to generate
clear, concise business descriptions for database tables and columns.
Base descriptions ONLY on the information provided. If you cannot determine
the meaning, say "Business purpose unknown."

Context for table {{TABLE_NAME}}:
- Schema: {{SCHEMA_NAME}}
- Columns:
{% for col in COLUMNS %}
  - {{col.name}} ({{col.data_type}})
    {% if col.is_pk %}PRIMARY KEY{% endif %}
    {% if col.fk_ref %}FK → {{col.fk_ref.table}}.{{col.fk_ref.column}}{% endif %}
{% endfor %}
- Row count: ~{{ROW_ESTIMATE}}
- Foreign keys referencing this table: {{REF_FKS}}

For each column, generate:
1. description: Business meaning (1 sentence max)
2. semantic_type: One of: identifier, name, description, amount, quantity,
   date, timestamp, boolean, code, status, contact, address, metric,
   dimension, foreign_key, unknown
3. pii: true if likely contains PII (name, email, phone, address, SSN)

Respond with JSON only.
```

#### Relationship Inference Algorithm

```python
def infer_relationships(tables: list[TableInfo]) -> list[InferredRelationship]:
    """
    Three strategies, combined with confidence scoring:
    
    1. Naming heuristic (confidence: 0.7):
       - If column C in table A is named exactly 'B_id' or '{singular(B)}_id'
         and table B exists, infer A.C → B.id
       - E.g., orders.customer_id → customers.id
       
    2. Reverse naming heuristic (confidence: 0.5):
       - If column C in table A is named 'id' and table B has column 'A_id',
         infer A.id → B.A_id
       - E.g., customers.id → orders.customer_id
       
    3. Column content overlap (confidence: 0.3):
       - If column C1 in table A has same name/type as column C2 in table B
         and both are PK/FK candidates
    """
    relationships = []
    
    # Strategy 1: Direct naming
    for table in tables:
        for col in table.columns:
            match = re.match(r'^(.+)_id$', col.name)
            if match:
                target_table = match.group(1)  # singularize
                if target_table in {t.name for t in tables}:
                    relationships.append(InferredRelationship(
                        source_table=table.name,
                        source_column=col.name,
                        target_table=target_table,
                        target_column='id',
                        confidence=0.7,
                        strategy='naming_heuristic'
                    ))
    
    # Deduplicate with existing FK relationships
    # Score fusion: if multiple strategies agree, confidence increases by 0.2
    # Threshold: confidence >= 0.5 accepted automatically
    #            confidence 0.3-0.5 accepted with human review flag
    #            confidence < 0.3 rejected
    
    return relationships
```

**Why not pure LLM for relationship inference?** LLMs hallucinate relationships (e.g., assuming `customer_name` relates to `customer_id`). Rule-based heuristics are deterministic and cheap. LLM is used only for tie-breaking when multiple strategies disagree.

### 3.8 Interfaces

```python
class SchemaIntelligence:
    """Enriches raw schema metadata with semantic understanding."""

    async def enrich_table(self, table: TableInfo, context: EnrichmentContext) -> EnrichedTable:
        """Generate table-level description and column descriptions."""
        pass

    async def enrich_schema(self, schema: ExtractionResult) -> EnrichmentResult:
        """Enrich all tables in a schema. Batch LLM calls."""
        pass

    async def infer_relationships(self, tables: list[TableInfo],
                                   existing_fks: list[Relationship]) -> list[InferredRelationship]:
        """Infer non-obvious relationships using heuristics + LLM."""
        pass

    async def classify_domain(self, table: TableInfo) -> DomainClassification:
        """Classify table into business domain."""
        pass
```

### 3.9 Failure Handling

| Failure Mode | Detection | Recovery |
|-------------|-----------|----------|
| LLM timeout (30s) | asyncio timeout | Retry once. If fails again, skip enrichment, use DDL-based fallback description. |
| LLM malformed JSON response | json.loads() exception | Retry with prompt reinforcement: "Respond with valid JSON only." |
| LLM hallucinated nonexistent columns | Schema validation (extracted columns set) | Strip hallucinated columns from output, log warning. |
| LLM refused to generate | Content filter triggered | Flag for human review, use DDL-based description. |
| Batch LLM partial failure | Per-table timeout | Return partial enrichment. Failed items retry on next sync. |

### 3.10 Metrics

| Metric | Type | Target |
|--------|------|--------|
| `enrichment.tables_per_second` | Gauge | > 5 tables/s |
| `enrichment.description_confidence` | Histogram | Mean > 0.8 |
| `enrichment.relationship_precision` | Gauge | > 0.8 |
| `enrichment.llm_success_rate` | Counter | > 95% |
| `enrichment.confidence_distribution` | Histogram | Monitor low-confidence drift |

### 3.11 Scaling

| Dimension | Strategy |
|-----------|----------|
| Batch size | 50 columns per LLM call (maximizes throughput, stays within 4K-token window) |
| Parallelism | 3 concurrent LLM calls (limited by GPU memory) |
| Incremental | Only re-enrich tables where DDL checksum changed |
| Cold start | Serial enrichment (no prior descriptions to reference) |

### 3.12 Testing

| Test Type | What It Tests |
|-----------|--------------|
| Unit | Relationship inference algorithm accuracy |
| Unit | Column semantic type classification |
| Integration | LLM response parsing (known good + bad responses) |
| Integration | Incremental enrichment (partial schema update) |
| Integration | PII detection confidence calibration |
| E2E | Full pipeline: extraction → enrichment → KE stores populated |

### 3.13 Dependencies

| Dependency | Reason |
|-----------|--------|
| LLM inference service | Description generation |
| KE API client | Read raw schema, write enriched schema |
| sqlglot | Fallback DDL parsing (if LLM unavailable) |
| Metadata Extraction output | Input schema data |

---

## 4. Business Ontology

### 4.1 Overview

Business Ontology is the layer that maps technical database artifacts to business concepts. It bridges the gap between "orders.total" (technical) and "monthly recurring revenue" (business). This is the core differentiator of the platform — no competitor offers an automated business ontology.

### 4.2 Responsibilities

1. Define business domains (sales, finance, HR, inventory, marketing)
2. Map tables to domains (automatic + manual override)
3. Define business terms and their technical mappings
4. Maintain glossary of business definitions
5. Support hierarchical domain trees
6. Enable cross-domain navigation (e.g., "revenue" → sales.finance)
7. Version ontology changes

### 4.3 Why Automated Ontology

**Without ontology**: User asks "show me revenue." The system searches for "revenue" in column/table names. If no column is named "revenue" (it might be "total_amount" or "net_sales"), the system fails.

**With ontology**: "revenue" is mapped to `orders.total` (where `status != 'refunded'`) and `invoices.amount`. The system can answer the question even when the database naming is cryptic.

**Why not require manual ontology setup?** That's what competitors do (manual YAML configuration). Our core differentiator is zero-configuration intelligence. The ontology must bootstrap automatically from schema analysis + query history and improve via the learning loop.

### 4.4 Inputs

```json
{
  "schema": {
    "tables": [
      {"name": "orders", "description": "Customer purchase orders",
       "columns": [{"name": "total", "description": "Order total amount", "semantic_type": "currency"}]}
    ]
  },
  "query_history": [
    {"natural": "show me monthly revenue", "sql": "SELECT date_trunc('month', created_at), SUM(total) FROM orders WHERE status != 'refunded'"}
  ],
  "existing_ontology": {
    "domains": [{"name": "sales", "description": "Revenue and customer metrics"}]
  }
}
```

### 4.5 Outputs

```json
{
  "domains": [
    {
      "id": "dom_001",
      "name": "sales",
      "description": "Revenue, customer acquisition, and order metrics",
      "parent_domain": null,
      "tables": ["customers", "orders", "order_items"],
      "terms": ["term_001", "term_002"]
    },
    {
      "id": "dom_002",
      "name": "finance",
      "description": "Accounting, budgets, and financial reporting",
      "parent_domain": null,
      "tables": ["invoices", "payments", "general_ledger"],
      "terms": ["term_003"]
    }
  ],
  "terms": [
    {
      "id": "term_001",
      "name": "revenue",
      "definition": "Total income from sales after refunds and discounts",
      "domain": "sales",
      "technical_mappings": [
        {
          "expression": "SUM(orders.total) WHERE orders.status != 'refunded'",
          "confidence": 0.85,
          "source": "query_history_mining"
        },
        {
          "expression": "SUM(invoices.amount) WHERE invoices.status = 'paid'",
          "confidence": 0.72,
          "source": "llm_inference"
        }
      ],
      "synonyms": ["sales", "income", "top_line"],
      "common_joins": ["customers JOIN orders", "orders JOIN order_items"]
    }
  ],
  "changes": [
    {"type": "added", "entity": "term", "name": "revenue", "confidence": 0.85}
  ]
}
```

### 4.6 Storage

| Data | Target Store | Representation |
|------|-------------|----------------|
| Domain definitions | Graph Store | `graph_nodes` (type='domain') + edges (type='belongs_to') |
| Business terms | Graph Store | `graph_nodes` (type='concept' or 'glossary_term') |
| Term-to-table mappings | Graph Store | edges (type='maps_to') |
| Domain hierarchy | Graph Store | edges (type='semantic_parent') |
| Query patterns | Graph Store | `graph_nodes` (type='query_pattern') + `frequently_joined` edges |

### 4.7 Algorithms

#### Domain Classification

```python
def classify_domain(table: TableInfo, all_tables: list[TableInfo]) -> str:
    """
    Classify a table into a business domain.
    
    Priority:
    1. Direct match: Table is named after a domain keyword
       (e.g., 'invoices' → 'finance')
    2. Column analysis: Most columns match a domain's semantic types
       (e.g., amounts, currencies → 'finance')
    3. Relationship analysis: Related tables already classified
       (e.g., 'order_items' related to 'orders' → 'sales')
    4. LLM fallback: Use LLM for ambiguous cases
    """
    domain_keywords = {
        'sales': ['customer', 'order', 'opportunity', 'quote', 'lead'],
        'finance': ['invoice', 'payment', 'budget', 'ledger', 'account', 'expense'],
        'hr': ['employee', 'payroll', 'timesheet', 'candidate', 'department'],
        'inventory': ['product', 'warehouse', 'stock', 'supplier', 'category'],
        'marketing': ['campaign', 'lead', 'email', 'subscriber', 'event'],
        'operations': ['shipment', 'facility', 'asset', 'maintenance', 'schedule'],
    }
    
    # Strategy 1: Direct match
    for domain, keywords in domain_keywords.items():
        for keyword in keywords:
            if keyword.lower() in table.name.lower():
                return domain, 0.8
    
    # Strategy 2: Column analysis
    domain_scores = {d: 0 for d in domain_keywords}
    for col in table.columns:
        for domain, keywords in domain_keywords.items():
            if any(kw in col.name.lower() for kw in keywords):
                domain_scores[domain] += 1
    
    if max(domain_scores.values()) > 0:
        best_domain = max(domain_scores, key=domain_scores.get)
        confidence = min(0.5 + 0.1 * domain_scores[best_domain], 0.95)
        return best_domain, confidence
    
    # Strategy 3: Relationship analysis (via graph traversal)
    # Strategy 4: LLM fallback (expensive, last resort)
    
    return 'unknown', 0.3
```

**Why multi-strategy?** No single strategy is reliable enough. Direct name matching catches obvious cases (85%+). Column analysis catches edge cases. Relationship analysis catches domain inheritance. LLM catches the remaining 5%.

### 4.8 Failure Handling

| Failure Mode | Recovery |
|-------------|----------|
| Domain unknown for table | Classify as 'unknown'. Learn from user query patterns. |
| Conflicting domain assignments | Higher confidence wins. Log conflict for review. |
| LLM term generation hallucination | Technical mapping validation against actual SQL execution. |
| Circular domain hierarchy | Cycle detection in graph traversal. Reject edge that creates cycle. |

### 4.9 Interfaces

```python
class OntologyBuilder:
    """Builds and maintains business ontology."""

    async def classify_domain(self, tables: list[TableInfo]) -> list[DomainClassification]: ...

    async def extract_terms(self, query_history: list[QueryRecord]) -> list[BusinessTerm]:
        """Mine business terms from natural language queries."""
        pass

    async def map_term(self, term: str, tables: list[TableInfo]) -> list[TechnicalMapping]:
        """Map a business term to SQL expressions."""
        pass

    async def reconcile(self, existing: Ontology, new: Ontology) -> OntologyDelta:
        """Merge new findings with existing ontology. Detect conflicts."""
        pass
```

---

## 5. Knowledge Graph

### 5.1 Overview

The Knowledge Graph is the interconnected representation of all business knowledge: tables, columns, domains, terms, query patterns, and their relationships. Stored in PostgreSQL using adjacency lists and recursive CTEs.

### 5.2 Why PostgreSQL (not Neo4j)

| Factor | PostgreSQL (recursive CTE) | Neo4j |
|--------|--------------------------|-------|
| Operations overhead | None (managed PG) | New cluster, backup, monitoring |
| Query depth | Excellent for depth ≤ 5 | Excellent for any depth |
| Transactional support | Native ACID | Requires bolt protocol |
| Deployment modes | Works in all 5 modes | Harder in air-gapped |
| Cost | Included in PG budget | +$500-2000/mo |

**Decision**: PostgreSQL for MVP (depth-limited queries). Migrate to Neo4j in Year 2 if:
- Traversal latency exceeds 500ms P95, OR
- Graph queries exceed 100 req/s per tenant, OR
- Traversal depth > 5 becomes common

### 5.3 Graph Schema

```
Node Types:
  table        — Database table
  column       — Database column (child of table)
  domain       — Business domain
  concept      — Business concept/entity
  glossary_term — Defined business term
  query_pattern — Recurring query structure

Edge Types:
  belongs_to       — column → table, node → domain
  references       — table → table (FK relationship)
  maps_to          — term → table/column
  frequently_joined — table ↔ table (join pattern)
  semantic_parent  — domain → subdomain
  equivalent_to    — term → term (synonyms)
```

### 5.4 Traversal Algorithms

#### Shortest Path (for join path discovery)

```sql
WITH RECURSIVE path AS (
    -- Base: start node
    SELECT id, id AS start_id, 0 AS depth, ARRAY[id] AS path_nodes
    FROM graph_nodes WHERE id = $1
    
    UNION ALL
    
    -- Recursive: follow edges
    SELECT e.target_node_id, p.start_id, p.depth + 1,
           p.path_nodes || e.target_node_id
    FROM path p
    JOIN graph_edges e ON e.source_node_id = p.id
    WHERE p.depth < $2  -- max depth
    AND NOT e.target_node_id = ANY(p.path_nodes)  -- no cycles
    AND e.edge_type IN ('references', 'frequently_joined')
)
SELECT * FROM path WHERE id = $3;  -- target node
```

**Why recursive CTE over application-level traversal?** PostgreSQL optimizes CTEs with materialization. Application-level traversal means N+1 queries. The CTE executes as a single query plan.

### 5.5 Interfaces

```python
class GraphStore:
    """Knowledge Graph operations."""

    async def create_node(self, node: GraphNode) -> GraphNode: ...
    async def create_edge(self, edge: GraphEdge) -> GraphEdge: ...
    async def get_node(self, node_id: UUID) -> GraphNode: ...
    async def get_edges(self, node_id: UUID, edge_types: list[str] = None) -> list[GraphEdge]: ...
    async def traverse(self, start_id: UUID, edge_types: list[str],
                       max_depth: int = 5) -> list[Path]: ...
    async def find_shortest_path(self, start_id: UUID, end_id: UUID) -> list[Path]: ...
    async def search_nodes(self, query: str, node_types: list[str] = None) -> list[GraphNode]: ...
    async def get_related_tables(self, table_id: UUID) -> list[TableRelation]: ...
    async def get_domain_tables(self, domain_id: UUID) -> list[UUID]: ...
```

---

## 6. Semantic Layer

### 6.1 Overview

The Semantic Layer sits between the raw Knowledge Graph and the Context Layer. It provides business-level abstractions: resolved terms, consistent naming, joined concepts, and context-aware disambiguation.

### 6.2 Responsibilities

1. Resolve business terms to technical mappings (e.g., "revenue" → `SUM(orders.total)`)
2. Disambiguate ambiguous terms based on query context
3. Provide consistent table/column naming (resolve acronyms, expand abbreviations)
4. Generate human-readable schema summaries
5. Cache resolved semantic lookups for performance

### 6.3 Why Separate from Context Layer?

The Semantic Layer is **offline computed** (ontology-driven). The Context Layer is **online retrieved** (query-driven). Separation means:
- Semantic resolution happens during ingestion, not during query time
- Heavy LLM calls for term resolution happen once, not per-query
- Semantic cache serves millions of queries without LLM latency

### 6.4 Term Resolution Algorithm

```python
def resolve_term(term: str, context: QueryContext, ontology: Ontology) -> ResolvedTerm:
    """
    Resolve a natural language term to a technical SQL expression.
    
    Steps:
    1. Exact match: Is term in ontology glossary?
    2. Synonym match: Does term have synonyms in ontology?
    3. Fuzzy match: Is term similar (edit distance, embedding) to known terms?
    4. Column match: Does any column name/description contain the term?
    5. Decomposition: Can the term be broken into table.column?
    
    Context disambiguation:
    - If "revenue" appears in a sales context → orders.total
    - If "revenue" appears in a finance context → invoices.amount
    - If no context → highest-confidence mapping
    """
    pass
```

### 6.5 Interfaces

```python
class SemanticLayer:
    """Provides business-level abstractions over technical schema."""

    async def resolve_term(self, term: str, domain: str = None) -> ResolvedTerm: ...
    async def resolve_terms_batch(self, terms: list[str], context: QueryContext) -> list[ResolvedTerm]: ...
    async def expand_abbreviation(self, abbr: str) -> str: ...
    async def get_table_summary(self, table_id: UUID) -> str: ...
    async def disambiguate(self, term: str, possible_mappings: list[TechnicalMapping],
                            context: QueryContext) -> TechnicalMapping: ...
    async def clear_cache(self, tenant_id: UUID) -> None: ...
```

---

## 7. Context Layer

### 7.1 Overview

The Context Layer is the **primary interface between the Knowledge Engine and the Query Pipeline**. When the Query Pipeline needs context for a natural language query, it calls the Context Layer. The Context Layer assembles schema context, business terms, relationships, and historical patterns into a single optimized payload for SQL generation.

### 7.2 Responsibilities

1. Accept a natural language query and retriever parameters
2. Call the Retriever (§9) for hybrid search results
3. Assemble context from multiple sources (schema, graph, history, terms)
4. Rank and prioritize context items by relevance
5. Manage context window (trim to fit LLM token limits)
6. Cache frequent context assemblies
7. Return structured context payload

### 7.3 Input

See [Retriever §9.4](#94-inputs) for the detailed input contract.

### 7.4 Output

```json
{
  "query_id": "qry_001",
  "context": {
    "primary_tables": [
      {
        "name": "customers",
        "id": "tbl_001",
        "ddl": "CREATE TABLE customers (id UUID PRIMARY KEY, ...)",
        "description": "Customer master data",
        "domain": "sales",
        "columns": [
          {"name": "id", "type": "uuid", "description": "Primary key"},
          {"name": "name", "type": "varchar(255)", "description": "Company name"}
        ],
        "relevance_score": 0.92
      }
    ],
    "relationships": [
      {"from": "orders.customer_id", "to": "customers.id", "type": "fk"}
    ],
    "business_terms": [
      {"term": "revenue", "mapping": "SUM(orders.total)", "confidence": 0.9}
    ],
    "query_patterns": [
      {"natural": "revenue by customer", "sql": "SELECT c.name, SUM(o.total)...",
       "frequency": 47}
    ],
    "schema_summary": {
      "database_name": "Production",
      "db_type": "postgresql",
      "total_tables": 142,
      "total_columns": 2840
    }
  },
  "stats": {
    "total_candidates": 85,
    "after_dedup": 42,
    "after_ranking": 25,
    "after_truncation": 18,
    "tokens_used": 6120,
    "total_time_ms": 185
  }
}
```

### 7.5 Context Assembly Algorithm

```python
async def assemble_context(query: str, params: RetrievalParams) -> ContextResult:
    """
    Step 1: Embed query → query vector
    Step 2: Hybrid search (vector + BM25 + graph) → candidates
    Step 3: Score fusion (RRF: reciprocal rank fusion)
    Step 4: Deduplicate (same source_id, higher score wins)
    Step 5: Enrich candidates with full metadata from Schema Store / Graph Store
    Step 6: Rank by relevance (see scoring weights in Retriever spec)
    Step 7: Truncate to max_tokens (prioritize: tables > relationships > terms > history)
    Step 8: Return assembled context
    """
    pass
```

### 7.6 Context Truncation Priority

When context exceeds the token limit, items are removed in this order (last removed first):

1. Query history patterns (least important for SQL generation)
2. Business terms with confidence < 0.5
3. Tables with relevance < 0.6
4. Column details for tables with relevance < 0.7 (keep table DDL, drop column list)
5. Relationships with confidence < 0.5

**Why this priority?** The SQL generator needs table DDL + column metadata most. Historical queries are helpful for pattern matching but not essential. Low-confidence terms may mislead.

### 7.7 Caching

Caching uses PostgreSQL-based query result caching. See [Cache Store](Database-Specification.md#13-cache-store) for details.

**Invalidation triggers**:
- Schema sync (full tenant cache flush)
- Learning loop enrichment (selective invalidation by table_id)
- Explicit admin action

### 7.8 Interfaces

```python
class ContextLayer:
    """Primary context assembly service."""

    async def get_context(self, query: str, params: RetrievalParams) -> ContextResult:
        """Full context assembly pipeline."""
        pass

    async def get_table_context(self, table_id: UUID) -> TableContext:
        """Get context for a specific table (for schema browsing UI)."""
        pass

    async def search_schemas(self, query: str, db_id: UUID = None) -> list[SchemaResult]:
        """Cross-database schema search (for schema browser UI)."""
        pass
```

---

## 8. Embedding Pipeline

### 8.1 Overview

The Embedding Pipeline converts text into dense and sparse vector representations using BGE-M3. Every schema element, query pattern, and business term gets embedded for semantic search.

### 8.2 Why BGE-M3

| Model | Dimensions | Dense+Sparse | Open Source | Latency | Quality |
|-------|-----------|-------------|-------------|---------|---------|
| BGE-M3 | 1024 | Yes (built-in SPLADE) | Yes (MIT) | 50ms/item | Top-3 MTEB |
| OpenAI ada-002 | 1536 | No | No | 100ms API | Good |
| e5-mistral-7b | 4096 | No | Yes | 500ms/item | Better quality, 5x slower |
| sentence-t5 | 768 | No | Yes | 30ms/item | Lower quality |

**Decision**: BGE-M3 for its unique combination of:
1. **Dense + sparse in one model**: SPLADE sparse vectors improve keyword matching without a separate BM25 index
2. **1024-dim balance**: Good quality without the storage cost of 4096-dim
3. **Self-hostable**: Runs on the same GPU infrastructure as inference models
4. **Multi-lingual**: 100+ languages, important for enterprise deployments

### 8.3 Responsibilities

1. Accept text content for embedding
2. Generate dense vector (1024-dim, normalized)
3. Generate SPLADE sparse vector (for hybrid search)
4. Batch processing for efficiency
5. Cache embeddings to avoid recomputation
6. Version tracking (embedding model version in metadata)

### 8.4 Inputs

```json
{
  "items": [
    {
      "id": "vec_001",
      "text": "customers: Customer master data with contact information. Columns: id (uuid, PK), name (varchar), email (varchar), created_at (timestamptz)",
      "content_type": "schema_element",
      "source_id": "tbl_001"
    }
  ],
  "model": "BAAI/bge-m3",
  "batch_size": 100
}
```

### 8.5 Outputs

```json
{
  "vectors": [
    {
      "id": "vec_001",
      "dense_vector": [0.012, -0.034, ..., 0.089],
      "sparse_vector": {
        "indices": [12, 45, 78, 234, 567],
        "values": [0.45, 0.32, 0.28, 0.22, 0.18]
      },
      "embedding_model": "BAAI/bge-m3-2026-01",
      "dimension": 1024,
      "normalized": true
    }
  ],
  "meta": {
    "batch_size": 100,
    "duration_ms": 450,
    "tokens_processed": 28400
  }
}
```

### 8.6 Embedding Text Construction

The text sent for embedding is constructed to maximize semantic signal:

```python
def build_embedding_text(table: Table, columns: list[Column]) -> str:
    """
    Format: {table_description}. Columns: {col_name} ({type}, {description})
    
    Why include type and description? 
    - Type helps distinguish semantic meaning (varchar 'status' vs integer 'status_code')
    - Description provides business context
    - Table description anchors the embedding in business domain
    """
    parts = [f"{table.name}: {table.description or ''}"]
    parts.append("Columns:")
    for col in columns:
        qualifiers = []
        if col.is_primary_key:
            qualifiers.append("PK")
        if col.foreign_key_table:
            qualifiers.append(f"FK->{col.foreign_key_table}.{col.foreign_key_column}")
        qualifier_str = f" ({', '.join(qualifiers)})" if qualifiers else ""
        parts.append(f"  {col.name} ({col.data_type}{qualifier_str}): {col.description or ''}")
    return "\n".join(parts)
```

### 8.7 Interfaces

```python
class EmbeddingPipeline:
    """Converts text to dense + sparse vectors."""

    async def embed(self, items: list[EmbeddingItem]) -> EmbeddingResult:
        """Batch embedding. Returns dense + sparse vectors."""
        pass

    async def embed_query(self, query: str) -> QueryEmbedding:
        """Embed a single query string. No caching."""
        pass

    def build_embedding_text(self, table: Table, columns: list[Column]) -> str:
        """Construct the text string for embedding."""
        pass
```

### 8.8 Performance Budget

| Operation | Latency | Batch Size | Throughput |
|-----------|---------|-----------|------------|
| Single query embedding | 30ms | 1 | 33 queries/s |
| Schema element embedding | 450ms | 100 | 220 items/s |
| Cold model load | 5s | — | Once per deployment |

---

## 9. Retriever

### 9.1 Overview

The Retriever is the core search engine. It combines vector similarity, keyword matching, and graph traversal to find relevant schema context for a natural language query.

### 9.2 Why Hybrid Search

| Strategy | Strength | Weakness |
|----------|----------|----------|
| Vector-only | Semantic understanding | Misses keyword-exact matches |
| BM25-only | Exact keyword matching | Misses semantic relationships |
| Graph-only | Relationship discovery | Requires starting point |
| **Hybrid (vector + BM25 + graph)** | All three strengths | Increased latency, complexity |

**Decision**: Hybrid with Reciprocal Rank Fusion. Each strategy covers different failure modes. RRF is a robust, parameter-free fusion method.

### 9.3 Retrieval Pipeline

```
Query: "Show revenue by customer for last quarter"

    │
    ▼
┌─────────────────────┐
│  1. Query Embedding  │  BGE-M3: query → dense vector (1024d)
│                      │          → sparse vector (SPLADE)
└──────────┬──────────┘
           │
           ▼
┌──────────────────────────────────────────────┐
│  2. Parallel Search (3 strategies)            │
│                                               │
│  ┌──────────────┐  ┌──────────┐  ┌────────┐ │
│  │ Vector Search │  │  BM25    │  │ Graph  │ │
│  │ (Qdrant)      │  │ (Qdrant  │  │Traverse│ │
│  │ top_k=50      │  │  sparse) │  │ depth=3│ │
│  │ .92, .88, ... │  │ .85, .82 │  │ .78... │ │
│  └──────────────┘  └──────────┘  └────────┘ │
└───────────────────┬──────────────────────────┘
                    │
                    ▼
┌──────────────────────────────┐
│  3. Score Fusion (RRF)       │
│  score = 1/(k + rank)        │
│  k = 60 (constant)           │
│  Normalize: [0, 1]           │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│  4. Metadata Enrichment      │
│  - Fetch full DDL from       │
│    Schema Store              │
│  - Fetch relationships from  │
│    Graph Store               │
│  - Fetch query patterns      │
│    from History Store        │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│  5. Ranking + Truncation     │
│  - Sort by fused score       │
│  - Deduplicate               │
│  - Apply context window      │
│    (max 8K tokens)           │
└──────────────┬───────────────┘
               │
               ▼
        Retrieved Context
```

### 9.4 Inputs

```json
{
  "query": "Show revenue by customer for last quarter",
  "query_id": "qry_001",
  "tenant_id": "tnt_001",
  "database_id": "db_001",
  "options": {
    "top_k_tables": 10,
    "top_k_columns": 25,
    "top_k_terms": 5,
    "top_k_history": 5,
    "max_tokens": 8192,
    "fusion_alpha": 0.75,
    "include_schema_ddl": true,
    "include_relationships": true,
    "include_business_terms": true,
    "include_query_history": true
  }
}
```

### 9.5 Scoring Weights (RRF Fusion)

| Signal | k Constant | Weight Multiplier | Rationale |
|--------|-----------|-------------------|-----------|
| Dense vector similarity | 60 | 1.0 | Primary signal for semantic understanding |
| BM25 keyword match | 60 | 0.8 | Higher weight for keyword-rich queries |
| Graph proximity | 60 | 0.6 | Relationship context as supporting signal |
| Query history frequency | 60 | 0.4 | Historical relevance as weak signal |
| Recency boost | 60 | 0.2 | Recent patterns get marginal boost |

The `k=60` constant is chosen per RRF best practices (small `k` emphasizes top ranks, large `k` smooths distribution). 60 provides balanced influence.

### 9.6 Performance Budget

| Stage | P50 | P95 | P99 |
|-------|-----|-----|-----|
| Query embedding | 30ms | 50ms | 100ms |
| Qdrant vector search | 30ms | 80ms | 150ms |
| Qdrant sparse search | 20ms | 50ms | 100ms |
| Graph traversal | 40ms | 100ms | 200ms |
| Score fusion + ranking | 10ms | 20ms | 50ms |
| Metadata enrichment | 30ms | 60ms | 120ms |
| Dedup + truncation | 10ms | 20ms | 50ms |
| **Total** | **170ms** | **380ms** | **770ms** |

---

## 10. Learning Engine

### 10.1 Overview

The Learning Engine closes the feedback loop. It processes user feedback to improve the Knowledge Engine over time. This is what makes the platform self-improving — every corrected query makes future queries better.

### 10.2 Why Batch-Only (No Online Learning)

**Online learning risk scenario**:
1. User submits malicious feedback (wrong SQL marked as "correct")
2. System immediately updates Knowledge Engine
3. Next 100 queries use the corrupted knowledge
4. Bad pattern propagates

**Batch learning with validation**:
1. User submits feedback
2. Feedback stored unprocessed
3. Every 5 minutes, batch processes all pending feedback
4. Each item validated (SQL parse check, consistency check, dedup)
5. Quality score computed
6. Only high-quality (>0.3) items incorporated
7. If multiple users confirm same correction, confidence increases

### 10.3 Processing Pipeline

```
Feedback Store → Collector → Validator → [QA Builder, Schema Enricher, Pattern Miner] → KE Update

Every 5 minutes:
1. SELECT unprocessed feedback, ordered by created_at, LIMIT 1000
2. Validate each item:
   - Parse corrected_sql (sqlglot)  
   - Check consistency with original query
   - Deduplicate (same user + query_id)
   - Compute quality_score
3. Route valid items:
   - has corrected_sql AND quality > 0.3 → Q&A Builder
   - has column clarification AND quality > 0.5 → Schema Enricher
   - pattern OR query history → Pattern Miner
4. Batch write updates to KE stores
5. Mark feedback as processed
```

### 10.4 Quality Scoring

| Signal | Weight | Notes |
|--------|--------|-------|
| corrected_sql provided | 0.4 | Concrete correction |
| corrected_sql parses | 0.2 | SQL is syntactically valid |
| comment > 20 chars | 0.1 | Thoughtful feedback |
| rating matches correction | 0.1 | Consistent |
| user history (trusted user) | 0.1 | Power users get priority |
| no prior bad feedback | 0.1 | Clean track record |

**Threshold**: quality_score ≥ 0.3 → process. Below 0.3 → archive with note.

### 10.5 Q&A Pair Builder

```python
def build_qa_pair(feedback: ValidatedFeedback, query: QueryRecord) -> QueryPattern:
    """
    Transform a corrected query into a reusable query pattern.
    
    Algorithm:
    1. Extract table references from corrected SQL (sqlglot AST)
    2. Normalize the SQL (remove literal values, parameterize filters)
    3. Extract intent from natural query
    4. Create graph_nodes (type: query_pattern)
    5. Create frequently_joined edges between referenced tables
    6. Increment frequency counter (or set to 1 if new)
    """
    pass
```

### 10.6 Schema Enricher

```python
def enrich_schema(feedback: ValidatedFeedback) -> SchemaEnrichment | None:
    """
    Determine if feedback implies a schema description improvement.
    
    Heuristics:
    1. User corrected a filter → check if column description mentions this filter
    2. User corrected a join → check if relationship description is clear
    3. User provided description → update column or table description
    
    Safety:
    - Requires 3+ independent corrections on same column within 7 days
    - New description must be consistent with existing descriptions
    - High-impact columns (PK, FK) require human review
    """
    pass
```

### 10.7 Patterns Engine

Continuously mines query history for patterns: frequent joins, common filter combinations, popular aggregations. Results stored as Graph Store edges and nodes for use by the Query Planner.

### 10.8 Learning Loop State Machine

```
CYCLE_START (5-min tick)
    │
    ▼
FEEDBACK_COLLECT (poll unprocessed)
    │
    ├── No items → CYCLE_END
    │
    ▼
FEEDBACK_VALIDATE (batch)
    │
    ├── All rejected → CYCLE_END (log metrics)
    │
    ▼
ROUTE_ITEMS
    │
    ├── Q&A items → BUILD_PAIRS → KE UPDATE
    ├── Schema items → ENRICH → KE UPDATE  
    └── Pattern items → MINE → KE UPDATE
    │
    ▼
MARK_PROCESSED
    │
    ▼
CYCLE_END (schedule next in 5 min)
```

---

## 11. Versioning

### 11.1 Why Versioning Matters

Enterprise schemas change. Tables are added, columns are renamed, data types change. Without versioning, the KE would be out of sync with reality. Versioning enables:

1. **Change detection**: Know what changed between syncs
2. **Rollback**: Revert schema knowledge if a sync was corrupted
3. **Audit**: Track when schema knowledge changed and why
4. **Incremental sync**: Only re-embed changed elements

### 11.2 Version Tracking

| Entity | Version Field | Incremented When |
|--------|--------------|------------------|
| `schema_infos` | `version` | DDL checksum changes |
| `tables` | `version` | Column added/removed/renamed |
| `graph_nodes` | `properties.version` | Content or embedding changes |
| `config` | `version` | Any config update |

### 11.3 Change Detection Algorithm

```python
def detect_changes(old_ddl: str, new_ddl: str) -> list[SchemaChange]:
    """
    1. Parse both DDLs to AST (sqlglot)
    2. Compare ASTs node by node
    3. Classify changes:
       - TABLE_ADDED: New table in DDL
       - TABLE_DROPPED: Table removed
       - COLUMN_ADDED: New column
       - COLUMN_DROPPED: Column removed
       - COLUMN_RENAMED: Column name changed (heuristic: same position, same type)
       - COLUMN_TYPE_CHANGED: Data type modified
       - COLUMN_NULLABLE_CHANGED: Null constraint modified
       - RELATIONSHIP_ADDED: New FK constraint
       - RELATIONSHIP_DROPPED: FK removed
    """
    pass
```

### 11.4 Version History Storage

```sql
CREATE TABLE schema_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schema_id UUID NOT NULL REFERENCES schema_infos(id),
    version INTEGER NOT NULL,
    changes JSONB NOT NULL,       -- array of SchemaChange objects
    ddl_snapshot TEXT,            -- full DDL at this version
    triggered_by VARCHAR(100),    -- connector, manual, llm
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(schema_id, version)
);
```

---

## 12. Context APIs

### 12.1 API Summary

All Context APIs are served through the KE API (port 8200). They are internal — not exposed to the public internet.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/context/retrieve` | Full context retrieval for a query |
| POST | `/v1/context/search` | Schema search (for UI) |
| GET | `/v1/context/table/{id}` | Context for a specific table |
| POST | `/v1/context/resolve` | Resolve a business term |
| POST | `/v1/context/enrich` | Trigger enrichment for a schema |
| POST | `/v1/context/sync` | Trigger full sync for a database |
| GET | `/v1/context/status` | Current index status metrics |

### 12.2 POST /v1/context/retrieve

See [Retriever §9.4 (Inputs)](#94-inputs) and [Context Layer §7.4 (Outputs)](#74-output).

**Performance**: P50 < 200ms, P95 < 500ms

### 12.3 POST /v1/context/search

**Purpose**: Search across all indexed content (for schema browser UI).

**Request**:
```json
{
  "query": "customer",
  "database_id": "db_001",
  "content_types": ["table", "column"],
  "limit": 20
}
```

**Response**:
```json
{
  "results": [
    {"type": "table", "name": "customers", "schema": "public",
     "description": "Customer master data", "score": 0.95},
    {"type": "column", "name": "customer_id", "table": "orders",
     "description": "FK to customers table", "score": 0.88}
  ]
}
```

### 12.4 POST /v1/context/resolve

**Purpose**: Resolve a business term to technical SQL.

**Request**:
```json
{
  "term": "monthly recurring revenue",
  "domain": "sales"
}
```

**Response**:
```json
{
  "resolved": true,
  "mappings": [
    {
      "expression": "SUM(orders.total) WHERE orders.type = 'subscription' AND orders.status != 'refunded'",
      "confidence": 0.82,
      "tables": ["orders"],
      "source": "query_history_mining"
    }
  ],
  "definition": "Total recurring revenue from active subscriptions, excluding one-time purchases and refunds",
  "synonyms": ["MRR", "subscription revenue"]
}
```

### 12.5 Status Endpoint

**Response**:
```json
{
  "stores": {
    "schema": {"status": "ok", "version": 5, "table_count": 2840},
    "vector": {"status": "ok", "collection_count": 142, "vector_count": 56800},
    "graph": {"status": "ok", "node_count": 12400, "edge_count": 45600},
    "history": {"status": "ok", "query_count": 125000},
    "feedback": {"status": "ok", "unprocessed": 42},
    "learning": {"status": "idle", "last_cycle": "2026-07-10T09:55:00Z"}
  }
}
```

---

## 13. Store Interface Reference

### 13.1 Unified Error Codes

| Code | Meaning | HTTP | Retryable |
|------|---------|------|-----------|
| KE-001 | Entity not found | 404 | No |
| KE-002 | Tenant ID required | 400 | No |
| KE-003 | Invalid service token | 401 | No |
| KE-004 | Store operation failed | 500 | Yes |
| KE-005 | Qdrant connection failed | 503 | Yes |
| KE-006 | PostgreSQL query failed | 503 | Yes |
| KE-007 | Cache write failed | 500 | Yes |
| KE-008 | Embedding service unavailable | 503 | Yes |

### 13.2 Common Headers

All KE API requests:
- `X-Service-Token: st_<uuid>` — Internal auth
- `X-Tenant-Id: tnt_001` — Tenant context (omit for global endpoints)
- `X-Request-Id: req_<ulid>` — Distributed tracing

### 13.3 Rate Limits

| Service | Limit | Window |
|---------|-------|--------|
| Schema Store reads | 1000 req/s | 1s |
| Schema Store writes | 100 req/s | 1s |
| Vector search | 500 req/s | 1s |
| Vector upsert | 100 req/s | 1s |
| Graph traversal | 200 req/s | 1s |
| Context retrieval | 200 req/s | 1s |

---

## 14. Cross-Cutting Concerns

### 14.1 Metrics (Prometheus)

| Metric | Source | Description |
|--------|--------|-------------|
| `ke_store_operation_duration_ms` | All stores | Per-store operation latency |
| `ke_store_operation_count` | All stores | Per-store operation count by status |
| `ke_embedding_duration_ms` | Embedding pipeline | Embedding latency |
| `ke_embedding_count` | Embedding pipeline | Items embedded |
| `ke_retrieval_duration_ms` | Retriever | Retrieval pipeline latency |
| `ke_retrieval_candidates` | Retriever | Candidate counts per stage |
| `ke_context_tokens_used` | Context Layer | Context window token count |
| `ke_learning_cycle_duration_ms` | Learning Engine | Batch cycle duration |
| `ke_learning_feedback_processed` | Learning Engine | Items processed per cycle |
| `ke_schema_version_current` | Schema Store | Current version per schema |

### 14.2 Logging

Every KE API operation logs:
```json
{
  "timestamp": "...",
  "level": "INFO",
  "service": "ke-api",
  "request_id": "req_abc",
  "tenant_id": "tnt_001",
  "store": "schema",
  "operation": "get_tables",
  "duration_ms": 15,
  "result": "success",
  "resource_id": "sch_001",
  "caller": "stores/schema/repository.py:142"
}
```

### 14.3 Tracing

OpenTelemetry spans for every KE API call:
- Root span: KE API endpoint
- Child spans: Store operation, Qdrant query, PostgreSQL query
- Events: Cache hit/miss, retry attempts

### 14.4 Security

- All KE API calls authenticated via service token
- All tenant-scoped operations checked against X-Tenant-Id
- All data modifications logged to audit store
- Query parameters NEVER include raw SQL (prevent injection via KE API)
- Service tokens rotated every 30 days
- KE API not exposed to public internet (internal service mesh only)

### 14.5 Scaling Limits

| Resource | Limit per KE API Instance |
|----------|--------------------------|
| Concurrent requests | 500 |
| Database connections | 50 (PgBouncer pooled) |
| Qdrant connections | 20 (gRPC) |
| Concurrent embedding calls | 4 (GPU memory) |
| Response body size | 10MB |
| Request body size | 1MB |
| Request timeout | 30s |
