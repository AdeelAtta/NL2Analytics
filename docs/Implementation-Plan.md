# Implementation Plan

**Enterprise Data Intelligence Platform — Phase 3 Implementation Blueprint**

| Metadata | Value |
|----------|-------|
| **Author** | Founding CTO |
| **Date** | July 2026 |
| **Status** | Draft |
| **Version** | 1.0 |
| **Architecture Version** | v1.0 |

---

## 1. Plan Overview

This document is the master blueprint for implementing the Enterprise Data Intelligence Platform (Architecture v1.0). It organizes all work into 17 epics, ~80 tasks, and 3 research spikes, designed for parallel execution by multiple AI coding agents and human engineers.

### 1.1 Key Constraints

| Constraint | Rule |
|------------|------|
| **No production code until Phase 4** | This phase produces plans, specs, templates, and project structure only |
| **Agent-safe parallelism** | Tasks have clear ownership, defined module boundaries, no overlapping responsibilities |
| **Architecture v1.0 is frozen** | Changes require documented ADRs in `/docs/decisions/` |
| **Every task has a definition of done** | No ambiguous handoffs between agents |
| **Epics** | 18 total (EP-001 through EP-018) — 8 complete, 1 in progress, 9 planned |

### 1.2 Directory Structure

```
/docs/
  Implementation-Plan.md          ← This file (master blueprint)
  System-Architecture.md          ← Phase 2 architecture (frozen)
  Knowledge-Engine.md             ← Phase 2 KE spec (frozen)
  Component-Design.md             ← Phase 2 component design (frozen)
  Data-Flow.md                    ← Phase 2 data flows (frozen)
  API-Design.md                   ← Phase 2 API contracts (frozen)
  Deployment-Architecture.md      ← Phase 2 deployment (frozen)
  Architecture-Review.md          ← Phase 2 review (frozen)
  
  /epics/                         ← 17 epic definitions
    EP-001-Dev-Environment.md
    EP-002-Schema-Store.md
    ... (one per epic)
  
  /tasks/                         ← ~80 individual implementation tasks
    TASK-001-Setup-Monorepo.md
    TASK-002-Define-CI-Pipeline.md
    ... (one per task)
  
  /agents/                        ← Agent prompts and specs
    agent-schema-intelligence.md
    agent-query-pipeline.md
    agent-frontend.md
    agent-infrastructure.md
  
  /decisions/                     ← Ongoing ADRs
    ADR-011-xxx.md
    ADR-012-xxx.md
  
  /progress/                      ← Progress tracking
    status-dashboard.md
  
  /templates/                     ← Templates for new work items
    template-task.md
    template-adr.md
    template-bug.md
    template-feature.md
```

### 1.3 Epic Overview

| ID | Epic | Priority | Dependencies | Est. Complexity | Agent |
|----|------|----------|-------------|-----------------|-------|
| EP-001 | Dev Environment & Monorepo | P0 | None | M | Infrastructure |
| EP-002 | Knowledge Engine — Schema Store | P0 | EP-001 | L | Knowledge Engine |
| EP-003 | Knowledge Engine — Vector Index | P0 | EP-001 | M | Knowledge Engine |
| EP-004 | Knowledge Engine — Knowledge Graph | P1 | EP-002 | M | Knowledge Engine |
| EP-005 | Knowledge Engine — API Layer | P0 | EP-002, EP-003 | XL | Knowledge Engine |
| EP-006 | Schema Intelligence Pipeline | P0 | EP-002, EP-003 | XL | Schema Intelligence |
| EP-007 | Context Retrieval | P0 | EP-005 | M | Query Pipeline |
| EP-008 | Intent Analysis & Planning | P0 | EP-007 | L | Query Pipeline |
| EP-009 | NL2SQL Generation | P0 | EP-008 | XL | Query Pipeline |
| EP-010 | Guardrail Stack | P0 | EP-002 | L | Query Pipeline |
| EP-011 | Query Executor | P0 | EP-010 | M | Query Pipeline |
| EP-012 | Learning Loop & Feedback | P1 | EP-005, EP-011 | L | Knowledge Engine |
| EP-013 | Public API Layer | P0 | EP-005, EP-011 | L | API |
| EP-014 | Frontend Application | P1 | EP-013 | XL | Frontend |
| EP-015 | Multi-Tenant Infrastructure | P0 | EP-001 | M | Infrastructure |
| EP-016 | CI/CD & Observability | P0 | EP-001 | M | Infrastructure |
| EP-017 | Research Spikes | P0 | None | M | Research |
| EP-018 | Core Services | P1 | EP-001 | S | Knowledge Engine |

### 1.4 Agent Assignments

| Agent | Owns Epics | Workspace |
|-------|-----------|-----------|
| **Infrastructure Agent** | EP-001, EP-015, EP-016 | `/infra/`, `.github/` |
| **Knowledge Engine Agent** | EP-002, EP-003, EP-004, EP-005, EP-012 | `/backend/ke/` |
| **Schema Intelligence Agent** | EP-006 | `/backend/schema-intelligence/` |
| **Query Pipeline Agent** | EP-007, EP-008, EP-009, EP-010, EP-011 | `/backend/query-pipeline/` |
| **API Agent** | EP-013 | `/backend/api/` |
| **Frontend Agent** | EP-014 | `/frontend/` |
| **Research Agent** | EP-017 | `/research/` |

---

## 2. Implementation Sequence

### 2.1 Phase 3 Work Plan (Parallel Tracks)

```
Week 1-2                        Week 3-4                         Week 5-6
┌─────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
│ EP-001: Dev Env │    │ EP-005: KE API       │    │ EP-007: Context Retr │
│ EP-015: Infra   │    │ EP-002: Schema Store │    │ EP-008: Intent/Plan  │
│ EP-016: CI/CD   │    │ EP-003: Vector Index │    │ EP-009: NL2SQL Gen   │
│ EP-017: Spikes  │    │ EP-006: Schema Intel │    │ EP-010: Guardrails   │
└─────────────────┘    └──────────────────────┘    └──────────────────────┘
                              │                             │
                              ▼                             ▼
                    ┌──────────────────────┐    ┌──────────────────────┐
                    │ EP-004: Knowledge    │    │ EP-011: Executor     │
                    │        Graph         │    │ EP-012: Learning     │
                    │ EP-013: Public API   │    │ EP-013: Public API   │
                    │                      │    │ EP-014: Frontend     │
                    └──────────────────────┘    └──────────────────────┘
```

### 2.2 Parallelism Model

| Track | Agent | Week 1-2 | Week 3-4 | Week 5-6 |
|-------|-------|----------|----------|----------|
| **Infrastructure** | Infra Agent | EP-001, EP-015, EP-016 | EP-015, EP-016 | EP-016 |
| **Knowledge Engine** | KE Agent | — | EP-002, EP-003, EP-005 | EP-004, EP-005, EP-012 |
| **Schema Intelligence** | Schema Agent | — | EP-006 | EP-006 |
| **Query Pipeline** | Pipeline Agent | — | — | EP-007, EP-008, EP-009, EP-010, EP-011 |
| **API** | API Agent | — | — | EP-013 |
| **Frontend** | Frontend Agent | — | — | EP-014 |
| **Research** | Research Agent | EP-017 | EP-017 | — |

### 2.3 Task Status Convention

Every task file uses this status convention:

| Status | Meaning |
|--------|---------|
| `backlog` | Defined but not started |
| `ready` | Dependencies met, available for pickup |
| `in_progress` | Currently being worked |
| `review` | Implementation complete, awaiting review |
| `done` | Reviewed and accepted |
| `blocked` | Waiting on dependency |

---

## 3. Module Boundaries

### No-Overlap Rules

| Module | Owns | Does NOT Own |
|--------|------|-------------|
| `/backend/ke/` | All knowledge stores and KE API | Pipeline logic, schema intelligence |
| `/backend/schema-intelligence/` | DB introspection, description generation, embedding | KE API, query pipeline |
| `/backend/query-pipeline/` | Intent, retrieval, planning, SQL gen, policy enforcement, execution | KE stores, public API |
| `/backend/api/` | Public REST API, auth middleware, rate limiting | Internal pipeline logic |
| `/frontend/` | React UI, state management, user flows | Backend services, APIs |
| `/infra/` | Docker, CI/CD | Application code |
| `/research/` | Experiments, benchmarks, evaluations | Production code |

### Shared Interfaces

| Interface | Defined In | Consumed By |
|-----------|-----------|-------------|
| Knowledge Engine API | `backend/ke/api/` | All backend services |
| Public REST API | `backend/api/routes/` | Frontend, external clients |
| Event Contracts | `backend/shared/events/` | Pipeline + Learning |
| Data Models | `backend/shared/models/` | All backend services |

---

## 4. Repository Structure

```
/                               ← Monorepo root
  package.json                  ← Workspace config (npm workspaces or nx)
  pyproject.toml                ← Python project config (uv/poetry)
  Makefile                      ← Top-level commands
  README.md
  
  /backend/
    /ke/                        ← Knowledge Engine
      /api/                     ← KE API service
      /stores/                  ← Store implementations
        /schema/                ← Schema store
        /vector/                ← Vector index (Qdrant removed)
        /graph/                 ← Knowledge graph
        /history/               ← Query history store
        /feedback/              ← Feedback store
        /config/                ← Configuration store
        /metrics/               ← Metric store
        /audit/                 ← Audit store
      /models/                  ← Data models (Pydantic)
      /migrations/              ← Alembic migrations
    /schema-intelligence/       ← Schema intelligence service
      /connectors/              ← DB connectors (SQLAlchemy)
      /parsers/                 ← DDL parsers
      /annotators/              ← LLM description generators
      /embedders/               ← BGE-M3 embedding service
      /inferers/                ← Relationship inference
    /query-pipeline/            ← Query pipeline services
      /intent/                  ← Intent agent
      /retrieval/               ← Context retrieval agent
      /planner/                 ← Query planner agent
      /generator/               ← NL2SQL generation agent
        /router/                ← Model router
        /candidates/            ← Candidate generator
        /selector/              ← Candidate selector
      /policy/                  ← Policy enforcement stack (10 layers)
      /executor/                ← Query executor
      /reflection/              ← Reflection agent
      /repair/                  ← Repair agent
    /api/                       ← Public API gateway
      /routes/                  ← Route handlers
      /middleware/              ← Auth, rate limit, logging
    /learning/                  ← Learning loop
      /collector/               ← Feedback collector
      /validator/               ← Feedback validator
      /builder/                 ← Q&A pair builder
      /enricher/                ← Schema enricher
      /miner/                   ← Pattern miner
    /shared/                    ← Shared code
      /models/                  ← Shared Pydantic models
      /events/                  ← Event schemas
      /utils/                   ← Shared utilities
      /clients/                 ← KE API client, DB clients
      /config/                  ← Base configuration
    /tests/                     ← Backend tests
      /unit/
      /integration/
      /e2e/
    
  /frontend/
    /src/
      /app/                     ← Next.js app router pages
      /components/              ← React components
        /ui/                    ← shadcn/ui primitives
        /chat/                  ← Chat interface
        /schema/                ← Schema browser
        /history/               ← Query history
        /settings/              ← Settings pages
        /admin/                 ← Admin dashboard
      /lib/                     ← Utilities
        /api-client/            ← API client
        /state/                 ← State management (Zustand)
      /styles/                  ← Tailwind CSS config
  
  /infra/
    /docker/                    ← Dockerfiles
    /docker/                    ← Dockerfiles (K8s, Terraform, Helm removed)
    
  /scripts/                     ← Utility scripts
  /.github/
    /workflows/                 ← CI/CD pipelines
    /actions/                   ← Custom actions
  
  /research/                    ← Research spikes
    /context-accuracy/
    /cold-start/
    /model-router/
  
  /docs/                        ← Documentation
    /epics/                     ← Epic definitions
    /tasks/                     ← Task files
    /agents/                    ← Agent prompts and specs
    /decisions/                 ← ADRs
    /progress/                  ← Progress tracking
    /templates/                 ← Templates
```

---

## 5. Technology Stack

| Layer | Technology | Version | Configuration |
|-------|-----------|---------|---------------|
| Python runtime | Python | 3.12+ | `pyproject.toml` (uv/poetry) |
| API framework | FastAPI | 0.115+ | `backend/api/` |
| Agent orchestration | LangGraph | latest | `backend/query-pipeline/` |
| ORM | SQLAlchemy | 2.0+ | `backend/ke/stores/` |
| DB driver (PG) | asyncpg | 0.30+ | `backend/ke/stores/` |
| Vector store client | Qdrant client (removed) | 1.12+ | `backend/ke/stores/vector/` |
| LLM inference | vLLM + SGLang | latest | — |
| Embeddings | BGE-M3 (sentence-transformers) | latest | `backend/schema-intelligence/embedders/` |
| SQL parser | sqlglot | latest | `backend/query-pipeline/policy/` |
| Frontend | React 19 + Next.js 15 | latest | `frontend/` |
| UI kit | shadcn/ui + Tailwind CSS | latest | `frontend/` |
| Docker | Docker | 27+ | `infra/docker/` |
| CI/CD | GitHub Actions | — | `.github/workflows/` |

---

## 6. Quality Gates

| Gate | Requirement | Enforced By |
|------|-------------|-------------|
| Type checking | mypy --strict passes | Pre-commit + CI |
| Linting | ruff passes | Pre-commit + CI |
| Unit tests | Coverage > 80% | CI |
| Integration tests | All KE store tests pass | CI |
| E2E tests | 10 benchmark queries pass | CI (nightly) |
| Security scan | Trivy: 0 critical | CI |
| Performance | API P95 < 200ms (baseline) | CI (benchmark) |

---

## 7. Directory Map for Agents

| Agent | Creates | Reads | Writes |
|-------|---------|-------|--------|
| **Infrastructure Agent** | `/infra/`, `/.github/`, `/scripts/` | `/docs/epics/EP-001`, EP-015, EP-016 | Task status in `/docs/tasks/` |
| **Knowledge Engine Agent** | `/backend/ke/` | `/docs/epics/EP-002`-EP-005, EP-012 | Task status |
| **Schema Intelligence Agent** | `/backend/schema-intelligence/` | `/docs/epics/EP-006` | Task status |
| **Query Pipeline Agent** | `/backend/query-pipeline/` | `/docs/epics/EP-007`-EP-011 | Task status |
| **API Agent** | `/backend/api/` | `/docs/epics/EP-013`, `/docs/API-Design.md` | Task status |
| **Frontend Agent** | `/frontend/` | `/docs/epics/EP-014`, `/docs/API-Design.md` | Task status |
| **Research Agent** | `/research/` | `/docs/epics/EP-017`, `/docs/Open-Questions.md` | Task status |

---

## 8. File Inventory

| Path | Content | Agent Owner |
|------|---------|-------------|
| `/docs/epics/EP-001-Dev-Environment.md` | Epic: Dev environment, monorepo, tooling setup | Infrastructure |
| `/docs/epics/EP-002-Schema-Store.md` | Epic: PostgreSQL schema store implementation | Knowledge Engine |
| `/docs/epics/EP-003-Vector-Index.md` | Epic: Qdrant vector index implementation (Qdrant removed) | Knowledge Engine |
| `/docs/epics/EP-004-Knowledge-Graph.md` | Epic: Business ontology and graph layer | Knowledge Engine |
| `/docs/epics/EP-005-KE-API.md` | Epic: Knowledge Engine API service | Knowledge Engine |
| `/docs/epics/EP-006-Schema-Intelligence.md` | Epic: Schema discovery, description, embedding | Schema Intelligence |
| `/docs/epics/EP-007-Context-Retrieval.md` | Epic: Hybrid context retrieval service | Query Pipeline |
| `/docs/epics/EP-008-Intent-Planning.md` | Epic: Intent analysis and query planning | Query Pipeline |
| `/docs/epics/EP-009-NL2SQL-Generation.md` | Epic: SQL generation with tiered model routing | Query Pipeline |
| `/docs/epics/EP-010-Guardrail-Stack.md` | Epic: 10-layer policy enforcement stack | Query Pipeline |
| `/docs/epics/EP-011-Query-Executor.md` | Epic: Query execution and result formatting | Query Pipeline |
| `/docs/epics/EP-012-Learning-Loop.md` | Epic: Feedback collection and continuous learning | Knowledge Engine |
| `/docs/epics/EP-013-Public-API.md` | Epic: Public REST API gateway | API |
| `/docs/epics/EP-014-Frontend.md` | Epic: Web application and user interfaces | Frontend |
| `/docs/epics/EP-015-Multi-Tenant-Infra.md` | Epic: Multi-tenant K8s infrastructure | Infrastructure |
| `/docs/epics/EP-016-CICD-Observability.md` | Epic: CI/CD pipelines and monitoring | Infrastructure |
| `/docs/epics/EP-017-Research-Spikes.md` | Epic: P0 research experiments | Research |
| `/docs/agents/agent-infrastructure.md` | Agent spec: Infrastructure | Infrastructure |
| `/docs/agents/agent-ke.md` | Agent spec: Knowledge Engine | Knowledge Engine |
| `/docs/agents/agent-schema-intelligence.md` | Agent spec: Schema Intelligence | Schema Intelligence |
| `/docs/agents/agent-query-pipeline.md` | Agent spec: Query Pipeline | Query Pipeline |
| `/docs/agents/agent-api.md` | Agent spec: API | API |
| `/docs/agents/agent-frontend.md` | Agent spec: Frontend | Frontend |
| `/docs/agents/agent-research.md` | Agent spec: Research | Research |
| `/docs/templates/template-task.md` | Template: Individual task | — |
| `/docs/templates/template-adr.md` | Template: Architecture decision record | — |
| `/docs/templates/template-bug.md` | Template: Bug report | — |
| `/docs/templates/template-feature.md` | Template: Feature request | — |
| `/docs/decisions/ADR-001-Knowledge-Engine-Architectural-Core.md` through `ADR-021-Multi-Turn-Session.md` | 21 ADRs covering architecture, tech stack, security, observability, and feature decisions | — |
| `/docs/progress/status-dashboard.md` | Progress tracking dashboard | — |
| `/docs/specifications/API-Specification.md` | OpenAPI contracts, error catalog | — |
| `/docs/specifications/Database-Specification.md` | All DB schemas, indexes, partitions, RLS | — |
| `/docs/specifications/Frontend-Specification.md` | Component hierarchy, state, flows | — |
| `/docs/specifications/KnowledgeEngine-Specification.md` | KE store interfaces, state machines | — |
| `/docs/specifications/Planner-Specification.md` | Planner I/O contracts, validation | — |
| `/docs/specifications/Retriever-Specification.md` | Retrieval pipeline, scoring, caching | — |
| `/docs/specifications/Deployment-Specification.md` | Configuration matrix, all modes | — |
| `/docs/specifications/Security-Specification.md` | STRIDE threat model, RBAC, isolation | — |
| `/docs/specifications/Observability-Specification.md` | Metrics, logs, traces, SLOs | — |
| `/docs/specifications/Sequence-Diagrams.md` | All workflows (query, sync, learning, error) | — |
| `/docs/specifications/State-Machines.md` | All state machines (query, sync, feedback, etc.) | — |
| `/docs/specifications/Performance-Budgets.md` | Per-component latency targets | — |
| `/docs/specifications/Cost-Budgets.md` | Per-query cost model, infrastructure cost | — |

---

## 3.5 Architecture & Implementation Readiness Review

Phase 3.5 verifies that the complete engineering blueprint answers all questions an engineer or AI agent might have before writing code. The following specifications collectively serve as the engineering bible — no architect questions should be needed during Phase 4 implementation.

| Specification | What It Answers |
|--------------|-----------------|
| API-Specification.md | Every endpoint, schema, error code, auth requirement |
| Database-Specification.md | Every table, index, constraint, migration, RLS policy |
| Frontend-Specification.md | Every component, state store, user flow |
| KnowledgeEngine-Specification.md | Every KE store interface, operation, error |
| Planner-Specification.md | Planner input/output contracts, validation rules |
| Retriever-Specification.md | Retrieval pipeline, scoring algorithm, caching |
| Deployment-Specification.md | Config per environment + deployment mode |
| Security-Specification.md | Threat model, attack mitigations, RBAC |
| Observability-Specification.md | Metrics, logs, traces, dashboards, alerts, SLOs |
| Sequence-Diagrams.md | All workflows with every service interaction |
| State-Machines.md | All entity lifecycles with state transitions |
| Performance-Budgets.md | Per-component latency targets (P50/P95/P99) |
| Cost-Budgets.md | Per-query cost model, infrastructure cost per tenant |

## 4. Phase 4 Readiness Checklist

The project is ready for implementation (Phase 4) when:

- [ ] All 14 specification documents exist in `/docs/specifications/`
- [ ] No engineer/agent would need to ask a question not answered by these specs
- [ ] Every API endpoint has a defined contract
- [ ] Every database table has a defined schema
- [ ] Every workflow has a sequence diagram
- [ ] Every stateful entity has a state machine
- [ ] Every error has a catalog entry
- [ ] Every config has a specification
- [ ] Every performance target is documented
- [ ] Every cost is estimated
- [ ] Every security threat has a mitigation

---

## 9. References

| Source | Relevance |
|--------|-----------|
| [System-Architecture.md](./System-Architecture.md) | Architecture v1.0 (frozen) |
| [Knowledge-Engine.md](./Knowledge-Engine.md) | KE specification (frozen) |
| [Component-Design.md](./Component-Design.md) | Component design (frozen) |
| [Data-Flow.md](./Data-Flow.md) | Data flows (frozen) |
| [API-Design.md](./API-Design.md) | API contracts (frozen) |
| [Deployment-Architecture.md](./Deployment-Architecture.md) | Deployment design (frozen) |
| [Architecture-Review.md](./Architecture-Review.md) | Architecture review (frozen) |
| [Epics: EP-001](./epics/EP-001-Dev-Environment.md) through [EP-017](./epics/EP-017-Research-Spikes.md) | Individual epic definitions |
| [Agents](./agents/) | Agent specifications and prompts |
| [Tasks](./tasks/) | Individual implementation tasks |
| [Decisions/ADR-011](./decisions/ADR-011-Tech-Stack.md) | Technology stack decisions |
| [Specifications: AI-Agent-Specification.md](./specifications/AI-Agent-Specification.md) | 10-agent pipeline, QueryState, contracts |
| [Specifications: API-Specification.md](./specifications/API-Specification.md) | Full API contracts |
| [Specifications: Database-Specification.md](./specifications/Database-Specification.md) | Database schemas |
| [Specifications: KnowledgeEngine-Specification.md](./specifications/KnowledgeEngine-Specification.md) | KE stores, API, extraction |
| [Specifications: Planner-Specification.md](./specifications/Planner-Specification.md) | Planner agent internals |
| [Specifications: Retriever-Specification.md](./specifications/Retriever-Specification.md) | Retriever agent internals |
| [Specifications: Schema-Specification.md](./specifications/Schema-Specification.md) | Schema store model |
| [Specifications: ModelRouter-Specification.md](./specifications/ModelRouter-Specification.md) | Model routing logic |
| [Specifications: Deployment-Specification.md](./specifications/Deployment-Specification.md) | Deployment config matrix |
| [Specifications: Frontend-Specification.md](./specifications/Frontend-Specification.md) | Frontend components, tests |
| [Specifications: Infrastructure-Specification.md](./specifications/Infrastructure-Specification.md) | K8s, networking, storage |
| [Specifications: Engineering-Standards.md](./specifications/Engineering-Standards.md) | Code standards, CI/CD |
| [Specifications: Workflow-Orchestrator-Specification.md](./specifications/Workflow-Orchestrator-Specification.md) | Pipeline orchestration |
| [Specifications: Performance-Budgets.md](./specifications/Performance-Budgets.md) | Performance targets |
| [Specifications: Cost-Budgets.md](./specifications/Cost-Budgets.md) | Cost model |
| [Specifications: Security-Specification.md](./specifications/Security-Specification.md) | Security review |
| [Specifications: Observability-Specification.md](./specifications/Observability-Specification.md) | Observability plan |
| [Specifications: Sequence-Diagrams.md](./specifications/Sequence-Diagrams.md) | All workflows |
| [Specifications: State-Machines.md](./specifications/State-Machines.md) | All state machines |
