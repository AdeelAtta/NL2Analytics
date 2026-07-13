# System Architecture

**Enterprise Data Intelligence Platform — Phase 2 Architecture & Design**

| Metadata | Value |
|----------|-------|
| **Author** | Founding CTO |
| **Date** | July 2026 |
| **Status** | Draft |
| **Version** | 1.0 |
| **Cross-References** | [Knowledge-Engine.md](./Knowledge-Engine.md), [Component-Design.md](./Component-Design.md), [Data-Flow.md](./Data-Flow.md), [API-Design.md](./API-Design.md), [Deployment-Architecture.md](./Deployment-Architecture.md) |

> **Note:** Redis and Qdrant were removed during cleanup — the stack uses PostgreSQL only. All references below to Redis/Qdrant/vector search are historical design documents; the current implementation has removed these dependencies.

---

## 1. Architectural Philosophy

### 1.1 The Knowledge Engine, Not the SQL Generator

Most NL2SQL products are built as **SQL generation pipelines** — take natural language, augment with schema context, generate SQL, execute, return results. The product IS the pipeline. Every feature is a pipeline stage.

This architecture fails for two reasons:

| Failure | Why It Fails |
|---------|--------------|
| **Brittle evolution** | Adding new capabilities (dashboards, alerts, agents) requires restructuring the pipeline. Each new feature becomes a pipeline hack. |
| **Lost knowledge** | Schema context, query history, feedback, and business meaning are ephemeral — created per-query and discarded. No cumulative intelligence. |

We invert this. The **Enterprise Knowledge Engine (EKE)** is the architectural core. Everything else is a consumer or producer of the Knowledge Engine.

```
┌─────────────────────────────────────────────────────────┐
│                   ENTERPRISE KNOWLEDGE ENGINE            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐  │
│  │  Schema  │  │  Query   │  │ Business │  │Feedback │  │
│  │  Store   │  │History   │  │  Graph   │  │ Store   │  │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘  │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │  Vector  │  │ Embedding│  │  Metric  │              │
│  │  Index   │  │  Model   │  │  Store   │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└──────────────────────┬──────────────────────────────────┘
                       │
                       │ Knowledge Engine API
                       │
          ┌────────────┼────────────────┬────────────┐
          │            │                │            │
          ▼            ▼                ▼            ▼
   ┌──────────┐ ┌──────────┐    ┌──────────┐ ┌──────────┐
   │ Schema   │ │Context   │    │Query     │ │Learning  │
   │Intell.   │ │Retrieval │    │Planner   │ │Loop      │
   │(Producer)│ │(Consumer)│    │(Consumer)│ │(C+P)     │
   └──────────┘ └──────────┘    └──────────┘ └──────────┘
   ┌──────────┐ ┌──────────┐    ┌──────────┐ ┌──────────┐
   │NL2SQL    │ │Guardrails│    │Executor  │ │API + UI  │
   │Generator │ │(Consumer)│    │(Producer)│ │(C+P)     │
   │(Consumer)│ └──────────┘    └──────────┘ └──────────┘
   └──────────┘
```

### 1.2 Design Principles

| Principle | Meaning | Implication |
|-----------|---------|-------------|
| **Knowledge-First** | Every component reads from or writes to the Knowledge Engine. No component holds authoritative state. | The Knowledge Engine is the single source of truth. Components are stateless executors. |
| **Consumers and Producers** | Each component is classified as a Knowledge Engine consumer, producer, or both. | Clear contracts. Clear data ownership. No hidden dependencies. |
| **Deployment-Agnostic** | The architecture runs identically in cloud, VPC, on-prem, or air-gapped. | All knowledge stores are self-hosted. No external API dependencies for core flow. |
| **Evolvable** | Adding a new capability means adding a new consumer/producer — not restructuring the system. | The Knowledge Engine API is stable. Capabilities are pluggable. |
| **Observable** | Every Knowledge Engine interaction is logged, traced, and measurable. | Full audit trail. Performance monitoring. Debugging without reproduction. |

### 1.3 Architectural Goals

| Goal | Target | Measured By |
|------|--------|-------------|
| Query generation P95 < 2s | Knowledge Engine retrieval < 100ms | API latency monitoring |
| 100-table schema discovery < 5 min | Ingestion pipeline throughput | Ingestion timing |
| Stateless components | Zero in-memory state across restarts | Deployment test |
| Pluggable capability | New NL2SQL pipeline variant in < 1 week | Integration test |
| Deployment-portable | Same Docker image for cloud + VPC + on-prem | CI/CD pipeline |

---

## 2. The Enterprise Knowledge Engine (EKE)

The Knowledge Engine is not a single database. It is a **layered knowledge system** consisting of:

### 2.1 Knowledge Stores

| Store | Technology | Content | Purpose |
|-------|-----------|---------|---------|
| **Schema Store** | PostgreSQL | Tables, columns, types, constraints, relationships, indexes | Structured schema metadata. Source of truth for database structure. |
| **Vector Index** | (removed) | Formerly Qdrant — removed during cleanup. Semantic search was planned via column embeddings. | Superseded — the stack uses PostgreSQL only. |
| **Knowledge Graph** | PostgreSQL with recursive CTEs + adjacency | Business terms → schema elements, metric definitions, join paths | Business-level understanding. Resolve "revenue" to the correct columns across databases. |
| **Query History Store** | PostgreSQL (time-series partitioned) | Queries, results, execution metadata, performance stats | Pattern mining, learning, cost analysis. |
| **Feedback Store** | PostgreSQL | Corrections, approvals, ratings, user comments | Learning signal. Quality measurement. |
| **Metric Store** | PostgreSQL | Metric definitions, formulas, aggregation rules, owners | Consistent business metric computation across databases. |
| **Audit Store** | PostgreSQL (append-only, immutable) | All Knowledge Engine interactions, queries, policy enforcement events | Compliance. Security. Debugging. |
| **Configuration Store** | PostgreSQL | Tenant settings, RBAC policies, connection configs, feature flags | System management. No config files. |

### 2.2 Knowledge Engine API

The Knowledge Engine exposes a single unified API. Every component communicates through this API — never directly to a store.

| Operation | Description | Used By |
|-----------|-------------|---------|
| `resolve(term, context)` | Map a business term to physical schema elements | Planner, NL2SQL Generator |
| `retrieve(query_embedding, filters)` | Semantic search over knowledge stores | Context Retriever |
| `ingest(source_type, data)` | Add knowledge from a source (DDL, query log, doc) | Schema Intelligence, Learning Loop |
| `store(knowledge_type, data)` | Persist knowledge (feedback, metric, query) | Executor, Learning Loop, Feedback |
| `query(knowledge_query)` | Structured query over any knowledge store | All components |
| `refresh(scope)` | Rebuild/enrich knowledge for a scope | Schema Intelligence, Learning Loop |
| `subscribe(event_type, callback)` | Event-driven knowledge change notification | All components |

### 2.3 Knowledge Lifecycle

```
                 ┌──────────────────┐
                 │  Raw Discovery   │  DDL introspection, query log scan, doc ingestion
                 └────────┬─────────┘
                          │
                          ▼
                 ┌──────────────────┐
                 │   Enrichment     │  LLM-based description generation, embedding creation
                 └────────┬─────────┘
                          │
                          ▼
                 ┌──────────────────┐
                 │   Validation     │  Human review, consistency checks, deduplication
                 └────────┬─────────┘
                          │
                          ▼
                 ┌──────────────────┐
                 │   Knowledge      │  Available for query via Knowledge Engine API
                 │   Activation     │
                 └────────┬─────────┘
                          │
                          ▼
                 ┌──────────────────┐
                 │   Feedback       │  User corrections, usage patterns, accuracy signals
                 └────────┬─────────┘
                          │
                          └──→ Back to Enrichment (continuous improvement loop)
```

**Detailed in**: [Knowledge-Engine.md](./Knowledge-Engine.md)

---

## 3. Component Architecture

Every component is classified by its relationship to the Knowledge Engine:

| Component | Role | Knowledge Engine Consumption | Knowledge Engine Production |
|-----------|------|------------------------------|----------------------------|
| Schema Intelligence | Producer | Reads raw DDL from databases | Writes schema store, knowledge graph |
| Context Retriever | Consumer | Reads schema store, query history | — |
| Query Planner | Consumer | Reads knowledge graph, schema store, metric store | — |
| NL2SQL Generator | Consumer | Reads context retriever output, planner output | — |
| Policy Enforcement | Consumer | Reads schema store, configuration store, RBAC policies | Writes audit store |
| Executor | Consumer + Producer | Reads policy enforcement output | Writes query history store, audit store |
| Learning Loop | Consumer + Producer | Reads feedback store, query history store | Writes knowledge graph, prompt store |
| API Layer | Consumer + Producer | Reads all stores (via API) | Writes knowledge engine API |
| UI | Consumer | Reads API layer | Writes API layer (user input) |
| Feedback Collector | Producer | — | Writes feedback store |

### 3.1 Schema Intelligence (Producer)

```
Databases ──► Connector ──► DDL Parser ──► Schema Store
                        ┌────┴────┐
                        │         │
                   Name Annot.   Relationship
                   (LLM)        Inference
                        │         │
                        └────┬────┘
                             ▼
                      Knowledge Graph
```

| Sub-Component | Function | Output |
|---------------|----------|--------|
| **Connector** | Introspect database schema via SQLAlchemy | Raw DDL, table/column lists |
| **DDL Parser** | Parse DDL into structured schema metadata | Schema objects, constraints, types |
| **Name Annotator** | LLM generates business descriptions for cryptic names | Column descriptions, table summaries |
| **Relationship Inferer** | Detect foreign key relationships from naming patterns + query history | Suggested joins, relationship confidence |
| **Embedder** | Create embeddings for schema elements + descriptions (removed with Qdrant) | Vector index entries |
| **Graph Builder** | Link business terms → schema elements in knowledge graph | Knowledge graph entries |

### 3.2 Context Retriever (Consumer)

```
User Query ──► Query Analyzer ──► Retriever ──► Ranker ──► Context
                                        │
                                   Schema Store
                                   Query History
```

| Sub-Component | Function |
|---------------|----------|
| **Query Analyzer** | Extract entities, intent, constraints from NL query |
| **Retriever** | Hybrid search (vector + keyword + structured) across knowledge stores |
| **Ranker** | Score and rank retrieved context by relevance to query |

### 3.3 Query Planner (Consumer)

```
User Query + Context ──► Intent Classifier ──► Decomposer ──► Planner
                                                              │
                                                   Knowledge Graph
                                                   Metric Store
                                                   Schema Store
```

| Sub-Component | Function |
|---------------|----------|
| **Intent Classifier** | Determine query type (simple SELECT, aggregation, multi-join, cross-DB, metric) |
| **Decomposer** | Break complex questions into sub-questions |
| **Join Path Finder** | Discover join paths across tables using knowledge graph |
| **Metric Resolver** | Map business metric names to their SQL definitions |

### 3.4 NL2SQL Generator (Consumer)

```
User Query + Context + Plan ──► Schema Linker ──► Candidate Generator ──► Selector
                                                                              │
                                                                         SQL Output
```

| Sub-Component | Function |
|---------------|----------|
| **Schema Linker** | Map NL terms to specific schema elements using context |
| **Candidate Generator** | Generate 3 SQL candidates using tiered model routing |
| **Selector** | Score candidates by confidence, cost, and execution risk |
| **Reflection Loop** | Re-run failed candidates with error feedback; re-rank |

### 3.5 Guardrail Stack (Consumer + Producer)

```
SQL ──► Intent ──► Sanitize ──► RBAC ──► Cost ──► Validate ──► Read-Only ──► Audit
                                           │
                                     Knowledge Engine
```

| Layer | Function | Source of Truth |
|-------|----------|-----------------|
| **L1: Intent Classification** | Is this a legitimate data query? | Knowledge Engine (query patterns) |
| **L2: Input Sanitization** | SQL injection, prompt injection? | Knowledge Engine (attack patterns) |
| **L3: RBAC Schema Scoping** | Can this user access these tables/columns? | Knowledge Engine (RBAC policies) |
| **L4: Query Cost Ceiling** | Will this query exceed cost/time limits? | Knowledge Engine (cost policies) |
| **L5: SQL Validation** | Is the SQL syntactically correct? | SQL parser |
| **L6: Read-Only Enforcement** | Does the SQL modify data? | SQL parser |
| **L7: Audit Logging** | Log everything for compliance. | Knowledge Engine (audit store) |

**Detailed in**: [Component-Design.md](./Component-Design.md)

### 3.6 Executor (Consumer + Producer)

```
SQL ──► Connection Pool ──► Database ──► Result ──► Formatter
                                              │
                                        Knowledge Engine
                                        (query history)
```

| Sub-Component | Function | Knowledge Engine Interaction |
|---------------|----------|------------------------------|
| **Connection Pool** | Manage database connections per tenant | Reads connection config from Configuration Store |
| **Query Runner** | Execute SQL against target database | — |
| **Result Formatter** | Format results for API response | — |
| **History Writer** | Log query + result + metadata | Writes Query History Store, Audit Store |
| **Cost Tracker** | Track query cost / resource usage | Writes Metric Store |

### 3.7 Learning Loop (Consumer + Producer)

```
Feedback ──► Collector ──► Validator ──► Transformer ──► Writer
                                                            │
                                                  Knowledge Engine
                                                  (vector + graph + prompts)
```

| Sub-Component | Function | Knowledge Engine Interaction |
|---------------|----------|------------------------------|
| **Feedback Collector** | Collect user corrections, approvals, ratings | Reads Feedback Store |
| **Feedback Validator** | Validate feedback quality (spam, low-effort) | — |
| **Q&A Pair Builder** | Transform validated feedback into Q&A pairs | Writes Vector Index |
| **Schema Enricher** | Use feedback to improve schema descriptions | Writes Schema Store |
| **Prompt Optimizer** | Update system prompts with successful patterns | Writes Configuration Store (prompts) |
| **Pattern Miner** | Discover common query patterns from history | Reads Query History, writes Knowledge Graph |

### 3.8 Feedback Collector (Producer)

```
UI ──► Correction ──► Approval ──► Rating ──► Feedback Store
```

### 3.9 API Layer (Consumer + Producer)

```
External ──► REST API ──► Auth ──► Rate Limit ──► Handler
                                                   │
                                             Knowledge Engine
```

### 3.10 UI (Consumer)

```
User ──► Web App ──► API Layer
```

---

## 4. Component Wiring Diagram

### Query Flow (Read Path)

```
User ──► UI/API ──► Query Analyzer ──► Context Retriever ──► Query Planner
                                                                    │
                                                                    ▼
                                                           NL2SQL Generator
                                                                    │
                                                                    ▼
                                                           Guardrail Stack
                                                                    │
                                                                    ▼
                                                              Executor
                                                                    │
                                                                    ▼
                                                           Result ──► User

         ── Knowledge Engine Read
         ── Data Flow
```

### Ingestion Flow (Write Path)

```
Database ──► Schema Intelligence ──► Knowledge Engine
BI Tool   ──► Connector          ──► Knowledge Engine
Docs      ──► Document Ingester  ──► Knowledge Engine
```

### Learning Flow (Feedback Path)

```
User Feedback ──► Feedback Collector ──► Learning Loop ──► Knowledge Engine
                                                                    │
                                                    ┌───────────────┤
                                                    ▼               ▼
                                            Schema Enriched    Prompt Updated
```

---

## 5. Deployment Abstraction

The architecture supports five deployment modes with zero code changes:

| Mode | Knowledge Engine Location | Inference Location | Database Connectivity |
|------|---------------------------|--------------------|----------------------|
| **Cloud SaaS** | Managed PostgreSQL on K8s | Self-hosted GPUs on K8s | Outbound to customer DB |
| **Dedicated Cloud** | Per-tenant PostgreSQL | Per-tenant GPU pool | Outbound to customer DB |
| **Customer VPC** | Deployed in customer's cloud account | Customer's GPU or cloud API | In-VPC connections |
| **On-Prem K8s** | Customer-managed PostgreSQL on their K8s | Customer GPU (AMD/NVIDIA) | Internal network |
| **Air-Gapped** | Fully self-contained, no external dependencies | Customer GPU | Internal network |

**Key**: The Knowledge Engine is always self-hosted. No external API dependencies for core functionality.

**Detailed in**: [Deployment-Architecture.md](./Deployment-Architecture.md)

---

## 6. Technology Stack Mapping

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Schema Intelligence** | Python 3.12, SQLAlchemy, LangGraph | Python for AI ecosystem. SQLAlchemy for DB abstraction. LangGraph for multi-step pipeline. |
| **Context Retriever** | LangChain, PostgreSQL | Qdrant removed — search uses PostgreSQL full-text. |
| **Query Planner** | LangGraph, Python | DAG-based planning with conditional branching. |
| **NL2SQL Generator** | LangGraph, vLLM, SGLang | Multi-agent pipeline. vLLM for inference serving. SGLang for structured output. |
| **Guardrail Stack** | Python, SQL parser (sqlparse/sqlglot) | Deterministic. No ML dependency for core layers. |
| **Executor** | Python, SQLAlchemy, asyncpg/psycopg | Connection pooling, async execution. |
| **Learning Loop** | Python, LangGraph | Pipeline orchestration (Qdrant removed). |
| **API Layer** | FastAPI, Python 3.12 | Async, auto-docs, Pydantic validation. |
| **UI** | React 19, Next.js 15, shadcn/ui, Tailwind CSS | Modern, accessible, server-side rendering. |
| **Knowledge Stores** | PostgreSQL 16 | Qdrant was removed — PostgreSQL only. |
| **Auth** | Auth0 / Clerk | SOC 2 compliant, SSO support. |
| **Infrastructure** | Kubernetes, Docker, Terraform | Cloud-agnostic, IaC. |

**Full recommendation details**: [Technology-Recommendations.md](./Technology-Recommendations.md)

---

## 7. Cross-Cutting Concerns

### 7.1 Multi-Tenancy

| Concern | Approach |
|---------|----------|
| **Data isolation** | Row-level tenant IDs in shared PostgreSQL |
| **Performance isolation** | Kubernetes pod resource limits + query cost ceilings per tenant |
| **Configuration isolation** | Per-tenant configuration records in Configuration Store |
| **Inference isolation** | Tenant-aware model routing; optional dedicated GPU pools for premium tenants |
| **Audit isolation** | Tenant ID on every audit record; queryable by tenant admin |

### 7.2 Observability

| Capability | Implementation |
|------------|---------------|
| **Distributed tracing** | OpenTelemetry across all components |
| **Metrics** | Prometheus metrics from every Knowledge Engine operation |
| **Logging** | Structured JSON logging, correlated by trace ID |
| **Alerting** | Grafana alerts on latency, error rate, policy enforcement events |
| **Debugging** | Per-query trace view in admin UI |

### 7.3 Security

| Layer | Implementation |
|-------|---------------|
| **Authentication** | JWT-based (Auth0/Clerk) for API + UI |
| **Authorization** | RBAC policies in Knowledge Engine Configuration Store |
| **Data encryption** | TLS in transit, AES-256 at rest |
| **Network security** | mTLS between components in same cluster |
| **Secrets management** | Kubernetes Secrets + Vault (Hashicorp) |

### 7.4 Scalability

| Component | Scalability Strategy |
|-----------|---------------------|
| **Knowledge Engine reads** | Read replicas for PostgreSQL |
| **Knowledge Engine writes** | Write master with async replication |
| **Schema Intelligence** | Horizontally scalable ingestion workers |
| **Context Retriever** | Stateless, horizontally scalable |
| **Query Planner** | Stateless, horizontally scalable |
| **NL2SQL Generator** | GPU-bound. Horizontal scaling with GPU pods. |
| **Guardrail Stack** | Stateless, horizontally scalable |
| **Executor** | Connection pool per tenant. Horizontally scalable workers. |
| **Learning Loop** | Queue-based (Kafka), horizontally scalable workers |
| **API Layer** | Stateless, horizontally scalable behind load balancer |

---

## 8. Evolutionary Path

The Knowledge Engine architecture is designed to evolve from Text-to-SQL to a full Enterprise Data Intelligence Platform:

| Capability | Phase | Knowledge Engine Impact |
|------------|-------|------------------------|
| NL2SQL | MVP | Knowledge Engine stores schema + query history |
| Multi-DB + Governance | Year 2 | Knowledge Engine adds cross-DB graph + RBAC policies |
| Dashboards + BI Integration | Year 2 | Knowledge Engine stores dashboard definitions + BI metadata |
| Proactive Insights | Year 3 | Knowledge Engine adds anomaly models + pattern detection |
| Agent Marketplace | Year 3 | Knowledge Engine exposes agent API + capability registry |
| Self-Service Analytics | Year 4 | Knowledge Engine adds semantic layer API + metric store |
| Autonomous Workflows | Year 5 | Knowledge Engine stores workflow definitions + triggers |

Each evolution adds new **knowledge types** and new **consumers/producers** — it never restructures the core architecture.

---

## 9. Architecture Decision Records

| ADR | Decision | Rationale | Alternatives Considered |
|-----|----------|-----------|------------------------|
| ADR-001 | Knowledge Engine is the single architectural core | All components must be consumers/producers of a unified knowledge system. Prevents pipeline-centric design that can't evolve. | Pipeline-centric architecture (rejected: brittle, can't evolve to platform) |
| ADR-002 | PostgreSQL only (Qdrant removed) | Qdrant was removed in cleanup — PostgreSQL handles all knowledge stores. No dedicated graph DB in MVP. | Neo4j (rejected: over-engineered for MVP, adds operational complexity), Pinecone (rejected: cloud-only, violates deployment-agnostic principle) |
| ADR-003 | Components are stateless executors | All state lives in the Knowledge Engine. Components can be killed and restarted without data loss. Scales horizontally. | Stateful components (rejected: complicates scaling, deployment) |
| ADR-004 | Knowledge Engine API is the only internal interface | No component talks to another component directly. No component reads a knowledge store directly. Enforces loose coupling. | Direct inter-component communication (rejected: tight coupling, hard to evolve) |
| ADR-005 | Self-hosted knowledge stores only | Core system must work in air-gapped environments. No external API dependency for Knowledge Engine operation. | Cloud-managed stores (rejected: violates deployment-agnostic principle) |
| ADR-006 | Tenant isolation at row/collection level | Avoids per-tenant infrastructure (cost) while maintaining isolation. | Per-tenant databases (rejected: operational cost at scale), shared everything (rejected: security concerns) |

---

## 10. References

| Source | Relevance |
|--------|-----------|
| [Knowledge-Engine.md](./Knowledge-Engine.md) | Detailed Knowledge Engine specification |
| [Component-Design.md](./Component-Design.md) | Detailed component design |
| [Data-Flow.md](./Data-Flow.md) | End-to-end data flow diagrams |
| [API-Design.md](./API-Design.md) | API contracts |
| [Deployment-Architecture.md](./Deployment-Architecture.md) | Infrastructure design |
| [Phase1-Executive-Review.md](./Phase1-Executive-Review.md) | Business context and MVP definition |
| [Technology-Recommendations.md](./Technology-Recommendations.md) | Technology stack rationale |
| [Technical-Landscape-Report.md](./Technical-Landscape-Report.md) | Foundational research |
