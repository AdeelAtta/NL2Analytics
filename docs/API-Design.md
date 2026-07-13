# API Design

**Enterprise Data Intelligence Platform — Phase 2 Architecture & Design**

| Metadata | Value |
|----------|-------|
| **Author** | Founding CTO |
| **Date** | July 2026 |
| **Status** | Draft |
| **Version** | 1.0 |
| **Cross-References** | [System-Architecture.md](./System-Architecture.md), [Knowledge-Engine.md](./Knowledge-Engine.md), [Component-Design.md](./Component-Design.md), [Data-Flow.md](./Data-Flow.md) |

---

## 1. API Architecture

### 1.1 Two API Layers

```
External Clients (UI, CLI, CI/CD, embedded, third-party)
         │
         │ HTTPS + JWT
         ▼
┌─────────────────────────────────────┐
│       PUBLIC API (port 8100)         │
│       FastAPI / REST + SSE           │
│       Auth, rate-limit, billing      │
└──────────────┬──────────────────────┘
               │
               │ mTLS (internal cluster)
               ▼
┌─────────────────────────────────────┐
│   KNOWLEDGE ENGINE API (port 8200)   │
│   FastAPI / gRPC                     │
│   Internal component communication   │
└──────────────┬──────────────────────┘
               │
               ▼
         Knowledge Stores
          (PostgreSQL only — Redis and Qdrant were removed)
```

### 1.2 Principles

| Principle | Rule |
|-----------|------|
| **Public API is stable** | Backward compatible. Versioned (`/v1/`). Deprecation notice: 6 months. |
| **Internal API is flexible** | No backward compatibility guarantee for internal KE API. Components deploy together. |
| **Knowledge Engine is the only internal interface** | No component talks to another component directly. No component reads a store directly. |
| **Async-first** | Long operations return `202 Accepted` with status endpoint. Stream via SSE. |
| **Idempotent where possible** | Retry-safe mutations. Idempotency keys for critical operations. |

### 1.3 Authentication

| API Layer | Method | Scope |
|-----------|--------|-------|
| Public API | JWT (Auth0/Clerk) | Per-user, per-tenant |
| Knowledge Engine API | mTLS (service mesh) | Internal component identity |
| Admin API | JWT + API key | Admin users, automation |

---

## 2. Public REST API (Port 8100)

### 2.1 Base URL

```
https://api.enterprise-data.ai/v1
```

### 2.2 Standard Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Authorization: Bearer <jwt>` | Yes | User JWT token |
| `X-Tenant-ID` | Yes | Tenant UUID |
| `X-Idempotency-Key` | For mutations | Retry-safe idempotency |
| `X-Trace-ID` | Recommended | Distributed tracing correlation |

### 2.3 Standard Response Envelope

```jsonc
// Success
{
  "data": { ... },
  "meta": {
    "trace_id": "uuid",
    "request_id": "uuid",
    "latency_ms": 245
  }
}

// Error
{
  "error": {
    "code": "RBAC_DENIED",
    "message": "Access to table 'hr.salaries' is restricted for your role",
    "details": { ... },
    "trace_id": "uuid"
  }
}
```

### 2.4 Query Endpoints

#### `POST /v1/query`

Execute a natural language query.

```jsonc
// Request
{
  "question": "show me revenue by month for 2025",
  "database_id": "uuid",
  "options": {
    "max_results": 1000,
    "include_sql": true,
    "include_explanation": true,
    "include_alternatives": false,
    "model_tier": "auto"  // auto | cheap | accurate
  }
}

// Response
{
  "data": {
    "query_id": "uuid",
    "sql": "SELECT DATE_TRUNC('month', created_at) AS month, SUM(amount) AS revenue FROM orders WHERE EXTRACT(YEAR FROM created_at) = 2025 GROUP BY month ORDER BY month",
    "explanation": "I grouped orders by month and summed the amount column to calculate monthly revenue for 2025.",
    "columns": [
      {"name": "month", "type": "timestamp"},
      {"name": "revenue", "type": "numeric"}
    ],
    "rows": [
      {"month": "2025-01-01", "revenue": 1250000.00},
      {"month": "2025-02-01", "revenue": 1180000.00}
    ],
    "row_count": 12,
    "execution_time_ms": 245,
    "total_latency_ms": 1850,
    "model_used": "qwen2.5-72b",
    "policy_results": {
      "intent": {"passed": true},
      "rbac": {"passed": true, "tables_accessed": 1},
      "cost": {"passed": true, "estimated_rows": 15000}
    },
    "alternatives": [  // if include_alternatives: true
      {"sql": "SELECT ...", "explanation": "...", "confidence": 0.82}
    ]
  },
  "meta": {
    "trace_id": "uuid",
    "latency_ms": 1850
  }
}

// Error: Guardrail blocked
{
  "error": {
    "code": "GUARDRAIL_BLOCKED",
    "message": "This query would access salary data, which your role doesn't have permission to view.",
    "details": {
      "blocked_by": "L3: RBAC Schema Scoping",
      "resource": "table: hr.employee_salaries",
      "user_role": "business_analyst",
      "suggestion": "Try asking about department-level aggregates instead."
    }
  }
}
```

#### `POST /v1/query/stream`

Execute query with SSE streaming for progressive results.

```
Event: query.received
Data: {"query_id": "uuid", "status": "analyzing"}

Event: query.analyzed
Data: {"intent": "aggregation", "entities": ["revenue", "month"], "tables": ["orders"]}

Event: query.sql_generated
Data: {"sql": "SELECT ...", "model_used": "qwen2.5-72b"}

Event: query.policy_check
Data: {"layer": "rbac", "passed": true}

Event: query.executing
Data: {"database_id": "uuid", "estimated_rows": 15000}

Event: query.row_batch
Data: {"batch": [{"month": "2025-01-01", "revenue": 1250000}, ...], "batch_number": 1, "total_batches": 2}

Event: query.complete
Data: {"row_count": 12, "execution_time_ms": 245, "total_latency_ms": 1850}
```

#### `POST /v1/query/explain`

Return SQL + reasoning without executing.

```jsonc
// Request body same as /v1/query with include_execution: false
{
  "question": "show me revenue by month for 2025",
  "database_id": "uuid"
}

// Response
{
  "data": {
    "sql": "SELECT DATE_TRUNC('month', created_at) AS month, SUM(amount) AS revenue ...",
    "explanation": "I'll group orders by month and sum the amount column.",
    "plan": {
      "tables_used": ["orders"],
      "join_path": [],
      "aggregations": [{"function": "SUM", "column": "orders.amount"}],
      "filters": {"orders.created_at": {"year": 2025}}
    },
    "confidence": 0.92,
    "model_used": "qwen2.5-72b",
    "estimated_cost_usd": 0.0042,
    "estimated_execution_time_ms": 200
  }
}
```

### 2.5 Schema Endpoints

#### `GET /v1/databases`

```jsonc
// Response
{
  "data": [
    {
      "id": "uuid",
      "name": "Production Postgres",
      "db_type": "postgresql",
      "status": "connected",
      "table_count": 145,
      "last_introspected_at": "2026-07-10T12:00:00Z",
      "created_at": "2026-06-01T00:00:00Z"
    }
  ]
}
```

#### `GET /v1/databases/{id}/tables`

```jsonc
// Query params: ?search=revenue&include_columns=true&include_descriptions=true

{
  "data": [
    {
      "id": "uuid",
      "table_name": "orders",
      "schema_name": "public",
      "description": "Customer order records with line item details",
      "row_count_estimate": 1500000,
      "is_view": false,
      "columns": [
        {
          "id": "uuid",
          "column_name": "amount",
          "data_type": "numeric",
          "is_primary_key": false,
          "is_nullable": false,
          "description": "Net order amount after discount in USD",
          "business_name": "Revenue",
          "is_pii": false,
          "tags": ["revenue", "financial"]
        }
      ]
    }
  ]
}
```

#### `GET /v1/databases/{id}/relationships`

```jsonc
{
  "data": [
    {
      "source_table": "orders",
      "source_column": "customer_id",
      "target_table": "customers",
      "target_column": "id",
      "relationship_type": "foreign_key",
      "confidence": 1.0,
      "detection_method": "ddl_constraint"
    },
    {
      "source_table": "orders",
      "source_column": "region_id",
      "target_table": "regions",
      "target_column": "id",
      "relationship_type": "inferred_fk",
      "confidence": 0.85,
      "detection_method": "naming_pattern"
    }
  ]
}
```

#### `POST /v1/databases`

Connect a new database.

```jsonc
// Request
{
  "name": "Production Postgres",
  "db_type": "postgresql",
  "connection_config": {
    "host": "db.example.com",
    "port": 5432,
    "database": "production",
    "username": "reader",
    "password": "encrypted_via_vault",
    "ssl": true,
    "extra": {}
  },
  "introspect": true  // trigger immediate schema discovery
}

// Response (202 Accepted)
{
  "data": {
    "id": "uuid",
    "status": "connecting"
  },
  "meta": {
    "trace_id": "uuid"
  }
}
```

#### `DELETE /v1/databases/{id}`
#### `POST /v1/databases/{id}/refresh`

Trigger schema re-discovery.

### 2.6 Knowledge Endpoints

#### `POST /v1/knowledge/resolve`

Resolve a business term.

```jsonc
// Request
{
  "term": "monthly recurring revenue",
  "database_ids": ["uuid1", "uuid2"],  // optional scope
  "include_formula": true
}

// Response
{
  "data": {
    "term": "Monthly Recurring Revenue",
    "aliases": ["MRR", "monthly revenue", "subscription revenue"],
    "definition": "Sum of all active subscription amounts at month end",
    "formula": "SELECT SUM(amount) FROM subscriptions WHERE status = 'active' AND date_trunc('month', current_date) = date_trunc('month', subscription_date)",
    "mappings": [
      {
        "database_id": "uuid",
        "database_name": "Production Postgres",
        "table": "subscriptions",
        "column": "amount",
        "additional_filters": {"status": "active"},
        "confidence": 0.95
      }
    ],
    "dimensions": ["region", "plan_type", "cohort_month"],
    "owner": "finance@company.com",
    "refresh": "daily"
  }
}
```

#### `POST /v1/knowledge/search`

Semantic search over knowledge.

```jsonc
// Request
{
  "query": "revenue by region orders",
  "stores": ["schema", "qa_pairs"],
  "top_k": 10,
  "filters": {
    "database_ids": ["uuid"],
    "data_types": ["numeric"]
  }
}

// Response
{
  "data": [
    {
      "store": "schema",
      "score": 0.89,
      "payload": {
        "database": "Production Postgres",
        "table": "orders",
        "column": "amount",
        "description": "Net order amount",
        "data_type": "numeric"
      }
    },
    {
      "store": "qa_pairs",
      "score": 0.82,
      "payload": {
        "question": "show total revenue by region",
        "sql": "SELECT r.name, SUM(o.amount) FROM orders o JOIN regions r ON o.region_id = r.id GROUP BY r.name",
        "accuracy": 0.95
      }
    }
  ]
}
```

### 2.7 History & Feedback Endpoints

#### `GET /v1/query/history`

```jsonc
// Query params: ?page=1&per_page=20&from=2026-06-01&to=2026-07-01&status=success

{
  "data": [
    {
      "query_id": "uuid",
      "question": "show me revenue by month for 2025",
      "sql": "SELECT ...",
      "database_name": "Production Postgres",
      "execution_time_ms": 245,
      "status": "success" | "error" | "blocked",
      "user_rating": null | -1 | 0 | 1,
      "created_at": "2026-07-10T14:30:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 1542,
    "total_pages": 78
  }
}
```

#### `POST /v1/feedback`

Submit feedback on a query result.

```jsonc
// Request
{
  "query_id": "uuid",
  "type": "correction",
  "corrected_sql": "SELECT DATE_TRUNC('month', o.created_at) AS month, SUM(oi.amount) AS revenue FROM orders o JOIN order_items oi ON o.id = oi.order_id WHERE EXTRACT(YEAR FROM o.created_at) = 2025 GROUP BY month ORDER BY month",
  "rating": 1,
  "comment": "Needed to join order_items for line-level revenue"
}

// Response
{
  "data": {
    "feedback_id": "uuid",
    "status": "accepted"
  }
}
```

### 2.8 Admin Endpoints

#### `POST /v1/admin/databases`

Connect a database (admin).

#### `GET /v1/admin/usage`

```jsonc
// Response
{
  "data": {
    "query_count_today": 342,
    "query_count_this_month": 8452,
    "active_users_today": 23,
    "active_users_this_month": 87,
    "total_cost_usd": 42.50,
    "latency_p50_ms": 1200,
    "latency_p95_ms": 4500,
    "policy_block_rate": 0.02,
    "db_connections": 5
  }
}
```

#### `GET /v1/admin/audit`

```jsonc
// Query params: ?page=1&per_page=50&action=policy_blocked&from=...

{
  "data": [
    {
      "id": "uuid",
      "user_email": "alice@co.com",
      "action": "policy_blocked",
      "details": {
        "blocked_by": "L3: RBAC Schema Scoping",
        "resource": "table: hr.employee_salaries"
      },
      "created_at": "2026-07-10T14:30:00Z"
    }
  ]
}
```

#### `PUT /v1/admin/settings`

```jsonc
// Request
{
  "settings": {
    "query_timeout_seconds": 60,
    "max_results_per_query": 10000,
    "cost_limit_per_query": 0.10,
    "model_routing": "auto",
    "feedback_prompt_frequency": "end_of_session"
  }
}
```

---

## 3. Knowledge Engine Internal API (Port 8200)

### 3.1 REST Endpoints

(internal cluster only, mTLS required)

#### `POST /internal/v1/ke/resolve`

```jsonc
// Request
{
  "tenant_id": "uuid",
  "term": "monthly recurring revenue",
  "context": {
    "database_ids": ["uuid"],
    "user_role": "analyst"
  }
}
// Response — same structure as public POST /v1/knowledge/resolve
```

#### `POST /internal/v1/ke/retrieve`

```jsonc
{
  "tenant_id": "uuid",
  "query": "revenue by region orders",
  "query_embedding": [0.1, 0.2, ...],
  "stores": ["schema", "qa_pairs"],
  "top_k": 15,
  "filters": {
    "database_ids": ["uuid"],
    "min_confidence": 0.5
  }
}
```

#### `POST /internal/v1/ke/ingest`

```jsonc
{
  "tenant_id": "uuid",
  "source_type": "ddl_introspection",
  "source_id": "uuid",
  "data": { ... }
}
```

#### `POST /internal/v1/ke/store`

```jsonc
{
  "tenant_id": "uuid",
  "store": "query_log",
  "data": { ... }
}
```

#### `POST /internal/v1/ke/query`

```jsonc
{
  "tenant_id": "uuid",
  "store": "schema",
  "query": {
    "select": ["tables.id", "tables.table_name"],
    "filters": {"database_id": "uuid"},
    "limit": 100
  }
}
```

#### `POST /internal/v1/ke/refresh`

```jsonc
{
  "tenant_id": "uuid",
  "scope": {
    "database_id": "uuid",
    "refresh_types": ["descriptions", "embeddings"]
  }
}
```

### 3.2 gRPC Services

For high-throughput, low-latency internal communication:

#### `KnowledgeEngine` service (gRPC)

```protobuf
service KnowledgeEngine {
  rpc Resolve(ResolveRequest) returns (ResolveResponse);
  rpc Retrieve(RetrieveRequest) returns (RetrieveResponse);
  rpc Store(StoreRequest) returns (StoreResponse);
}

message ResolveRequest {
  string tenant_id = 1;
  string term = 2;
  Context context = 3;
}

message ResolveResponse {
  repeated Resolution resolutions = 1;
  int32 latency_ms = 2;
}
```

#### `Ingestion` service (gRPC)

```protobuf
service Ingestion {
  rpc IngestSchemas(IngestSchemasRequest) returns (IngestSchemasResponse);
  rpc IngestQueryLog(StoreRequest) returns (StoreResponse);
  rpc IngestFeedback(StoreRequest) returns (StoreResponse);
}
```

#### `Refresh` service (gRPC)

```protobuf
service Refresh {
  rpc RefreshDatabase(RefreshRequest) returns (RefreshResponse);
  rpc RefreshAll(RefreshAllRequest) returns (RefreshAllResponse);
}
```

---

## 4. Component-to-Knowledge Engine API Usage

| Component | KE Method | Endpoint | Frequency |
|-----------|-----------|----------|-----------|
| Schema Intelligence | `ingest` | `POST /internal/v1/ke/ingest` | Per DB connect + daily |
| Schema Intelligence | `refresh` | `POST /internal/v1/ke/refresh` | After ingestion |
| Context Retriever | `retrieve` | `POST /internal/v1/ke/retrieve` | Per query |
| Context Retriever | `query` (schema) | `POST /internal/v1/ke/query` | Per query |
| Query Planner | `resolve` | `POST /internal/v1/ke/resolve` | Per query (if terms detected) |
| Query Planner | `query` (graph) | `POST /internal/v1/ke/query` | Per query |
| NL2SQL Generator | (uses Context Retriever, not KE directly) | — | — |
| Guardrail Stack | `query` (RBAC) | `POST /internal/v1/ke/query` | Per query |
| Guardrail Stack | `store` (audit) | `POST /internal/v1/ke/store` | Per query |
| Executor | `store` (query_log) | `POST /internal/v1/ke/store` | Per query |
| Executor | `store` (audit) | `POST /internal/v1/ke/store` | Per query |
| Learning Loop | `query` (feedback) | `POST /internal/v1/ke/query` | Batch every 5min |
| Learning Loop | `store` (qa_pairs) | `POST /internal/v1/ke/store` | Per validated correction |
| Learning Loop | `refresh` | `POST /internal/v1/ke/refresh` | After enrichment |
| Feedback Collector | `store` (feedback) | `POST /internal/v1/ke/store` | Per user feedback |
| API Layer | (proxies to public API) | — | — |

---

## 5. Error Codes

| HTTP | Code | Meaning | Retryable |
|------|------|---------|-----------|
| 400 | `INVALID_INPUT` | Malformed request | No |
| 400 | `QUERY_TOO_LONG` | Input exceeds max length | No |
| 401 | `UNAUTHORIZED` | Missing/invalid JWT | No |
| 403 | `RBAC_DENIED` | Insufficient permissions | No |
| 403 | `POLICY_BLOCKED` | Query blocked by policy enforcement | No (rephrase) |
| 404 | `NOT_FOUND` | Resource not found | No |
| 409 | `CONFLICT` | Idempotency key conflict | No |
| 422 | `VALIDATION_ERROR` | Schema validation failed | No |
| 429 | `RATE_LIMITED` | Too many requests | Yes (backoff) |
| 500 | `INTERNAL_ERROR` | Unexpected server error | Yes |
| 502 | `DATABASE_UNREACHABLE` | Target DB not reachable | Yes |
| 503 | `SERVICE_UNAVAILABLE` | Temporary service outage | Yes |

---

## 6. Rate Limiting

| Tier | Limit | Burst |
|------|-------|-------|
| Free | 100 queries/month (total) | — |
| Starter | 200 queries/seat/month | 10/min |
| Pro | 1,000 queries/seat/month | 30/min |
| Enterprise | Custom | Custom |

Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

---

## 7. Pagination

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `per_page` | int | 20 | Items per page (max 100) |
| `from` | ISO8601 | — | Start date filter |
| `to` | ISO8601 | — | End date filter |
| `sort` | string | `created_at` | Sort field |
| `order` | asc\|desc | `desc` | Sort direction |

Response includes `meta.page`, `meta.per_page`, `meta.total`, `meta.total_pages`.

---

## 8. API Versioning

| Version | Status | Notes |
|---------|--------|-------|
| `v1` | Active (MVP) | Stable |
| `v2` | Planned (2027) | Breaking changes aggregated |

**Versioning strategy**: URL path versioning (`/v1/`, `/v2/`). At least 6 months overlapping support when introducing new version.

---

## 9. References

| Source | Relevance |
|--------|-----------|
| [System-Architecture.md](./System-Architecture.md) | Component architecture these APIs serve |
| [Component-Design.md](./Component-Design.md) | Component behavior behind each endpoint |
| [Knowledge-Engine.md](./Knowledge-Engine.md) | Internal KE API data models |
| [Data-Flow.md](./Data-Flow.md) | End-to-end flow triggered by each endpoint |
