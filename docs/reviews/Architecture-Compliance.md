# Architecture Compliance Report

**Project:** SchemaIntern
**Date:** 2026-07-11
**Status:** ❌ NON-COMPLIANT
**Score:** 55%

---

## Executive Summary

The implementation has significant architecture drift from the specified architecture. The planned microservices architecture (public-api, ke-api, query-pipeline, schema-intel, learning-loop, auth) has been collapsed into two monolithic FastAPI apps (`backend/app/` and `backend/ke/`). The query pipeline agents (intent, planner, generator, executor, policy) are embedded within `backend/ke/` instead of living in a separate `backend/query-pipeline/` service. The Learning Loop service, Public API, and Auth service are entirely unimplemented.

---

## Architecture Compliance Matrix

| Requirement | Specified | Implemented | Compliance |
|-------------|-----------|-------------|------------|
| Microservices separation | 6 services in `src/backend/` | 2 services (app + KE) | ❌ |
| KE API at `/backend/ke/` | Yes | Yes | ✅ |
| Public API at port 8100 | Yes | Not implemented | ❌ |
| KE API at port 8200 | Yes | Yes (via app/main.py) | ✅ |
| LangGraph agent orchestration | Yes | Not implemented (in-process) | ❌ |
| Intent agent as LangGraph node | Separate module | In `ke/services/intent.py` | ⚠️ |
| Planner agent as LangGraph node | Separate module | In `ke/services/planner.py` | ⚠️ |
| Generator agent as LangGraph node | Separate module | In `ke/services/generator.py` | ⚠️ |
| Executor agent as LangGraph node | Separate module | In `ke/services/executor.py` | ⚠️ |
| Policy enforcement as agent | Separate module | In `ke/services/policy/` | ⚠️ |
| Schema intelligence service | `backend/schema-intel/` | In `backend/schema_intelligence/` | ⚠️ |
| Learning loop service | `backend/learning-loop/` | Empty stub | ❌ |
| Auth service | `backend/auth/` | Empty stub | ❌ |
| Shared events module | `backend/shared/events/` | Not implemented | ❌ |
| Shared clients module | `backend/shared/clients/` | Not implemented | ❌ |
| Shared utils module | `backend/lib/utils/` | Empty | ❌ |
| Event bus (Redis Pub/Sub) | Specified | Not implemented | ❌ |
| WebSocket API | Specified | Not implemented | ❌ |
| Streaming (SSE) API | Specified | Not implemented | ❌ |
| Frontend at `/frontend/` | Yes | Scaffold only | ❌ |

---

## Dependency Direction Compliance

| Dependency | Direction | Compliant? | Notes |
|-----------|-----------|------------|-------|
| ke/stores/ → models/ | stores import models | ✅ | Correct |
| ke/services/ → stores/ | services import stores | ✅ | Correct |
| ke/api/routes/ → services/ | routes import services | ✅ | Correct |
| shared/ → anything | no imports from ke/ | ✅ | Correct |
| schema_intelligence/ → ke/ | should not depend | ✅ | No dependency |
| ke/ → shared/ | imports shared/models | ✅ | Correct |

---

## Layer Isolation

| Layer | Owns | Violations |
|-------|------|------------|
| `ke/api/routes/` | HTTP route handlers | None — no business logic in routes |
| `ke/services/` | Business logic | None — no HTTP awareness |
| `ke/stores/` | Data access | None — no HTTP or business logic |
| `ke/models/` | Data models | None — Pydantic only |
| `shared/models/` | Shared models | None |

---

## Folder Structure Compliance

| Specified Path | Actual Path | Status |
|----------------|-------------|--------|
| `src/backend/ke-api/` | `backend/ke/` | ❌ (different name) |
| `src/backend/query-pipeline/` | `backend/query-pipeline/app/` (empty) | ❌ (logic in ke/) |
| `src/backend/schema-intel/` | `backend/schema_intelligence/` | ❌ (naming mismatch) |
| `src/backend/public-api/` | `backend/public-api/app/` (empty) | ❌ |
| `src/backend/learning-loop/` | `backend/learning-loop/app/` (empty) | ❌ |
| `src/backend/auth/` | `backend/auth/app/` (empty) | ❌ |
| `src/backend/lib/` | `backend/lib/*/` (empty) | ❌ |
| `src/shared/` | `backend/shared/` | ⚠️ (different path) |
| `tests/` | `backend/tests/` + `tests/` | ⚠️ (split) |
| `infra/` | `infra/` | ✅ |
| `scripts/` at root | `scripts/` (empty) | ❌ |

---

## Undocumented Components

| Component | Documented? | Notes |
|-----------|-------------|-------|
| Observability (OpenTelemetry + Prometheus) | ⚠️ Partial | Implementation exists but no ADR |
| Query Quality Scorer | ❌ No | Feature not in any spec/task |
| Pipeline Orchestration (6-stage) | ⚠️ Partial | Architecture differs from spec |
| Schema-Aware Context Injection | ⚠️ Partial | Implementation differs from spec |
| Multi-Turn Session Service | ⚠️ Partial | Implementation differs from spec |
| PII Detection Service | ❌ No | Not in any spec |
| Ontology Service | ❌ No | Not in any spec |
| Alert Service | ❌ No | Not in any spec |

---

## Architecture Violations

1. **Query pipeline logic lives in KE service** — The intent, planner, generator, executor, and policy services are all under `backend/ke/services/` instead of a separate `backend/query-pipeline/`. This violates the module boundary rules in Implementation-Plan.md §3.

2. **LangGraph not used** — The AI-Agent-Specification.md §8 specifies LangGraph for agent orchestration with a `QueryState` object. The implementation uses simple function calls without LangGraph.

3. **Single FastAPI app instead of two** — The implementation has both the main app (health, auth, etc.) and the KE API in separate FastAPI apps but the README and Implementation-Plan specify `public-api` on port 8100 and `ke-api` on port 8200 as separate services.

4. **Missing shared interfaces** — No `shared/events/`, `shared/clients/`, or `shared/middleware/` exist as specified in Implementation-Plan.md §3.

5. **Undocumented extra features** — PII detection, Ontology service, Alerts service, Quality Scorer, and Observability additions exist without corresponding ADRs, breaking the architecture governance rules (Engineering-Standards.md §18.1 requires ADR for L3 decisions).

---

## Recommendations

1. Extract query-pipeline services to a separate `backend/query-pipeline/` package
2. Implement LangGraph-based agent orchestration as specified
3. Create the missing shared modules (`shared/events/`, `shared/clients/`)
4. Document all undocumented features via ADRs
5. Rename `schema_intelligence/` to match spec naming
6. Plan migration path to microservices for production
