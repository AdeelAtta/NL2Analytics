# Executive Due Diligence Report

**Project:** SchemaIntern — Enterprise Text-to-SQL SaaS Platform
**Date:** 2026-07-11
**Auditor:** Independent Technical Due Diligence Team
**Verdict:** CONDITIONAL PASS

---

## 1. Executive Summary

### 1.1 Is this genuinely a high-quality engineering project?

**PARTIALLY VERIFIED.** The backend demonstrates professional-grade architecture with clean layer separation, proper use of modern Python patterns (async/await, Pydantic v2, FastAPI, SQLAlchemy 2.0), and comprehensive test coverage (883 tests). The AI pipeline architecture is genuinely well-designed with a 10-layer guardrail stack, hybrid retrieval, and a self-learning loop. However, the codebase has significant technical debt: 168+ pre-existing Ruff E501 violations, pre-existing MyPy errors across 20+ files, and several architectural concerns around state management (in-memory-only stores for sessions, alerts, and users that don't persist across restarts without file-based JSON).

### 1.2 Would you invest in this startup based on the repository?

**CONDITIONAL YES.** The engineering team has built a solid foundation with genuine architectural sophistication in the AI pipeline (multi-tier model routing, reflection, guardrails). The 10-layer policy enforcement stack is enterprise-grade. However, the product is not yet production-ready — it lacks a proper frontend (React shell with stubs), has no multi-region deployment capability, and uses mock implementations for critical components (BGE-M3 embeddings, LLM inference). The competitive moat is in the schema adaptation and guardrail layers, but this needs to be validated against real enterprise benchmarks.

### 1.3 Would you approve it for an enterprise pilot?

**CONDITIONAL YES — with caveats.** Suitable for a controlled private beta with a single tenant. The security fundamentals are sound (JWT auth, SQL injection protection via sqlglot, rate limiting, API key auth). However, enterprise requirements missing: SSO/SAML, SOC 2 audit trails, immutable audit logs, data residency controls, and a proper admin UI. The system works without infrastructure in demo mode (mock data, dry-run execution), which is ideal for evaluation.

### 1.4 Top 10 Strengths

1. **10-layer policy enforcement stack** — Production-proven architecture (modeled after ASK-TARA with 90K queries, zero incidents). L2-L10 are fully deterministic (no LLM dependency).
2. **Comprehensive SQL injection protection** — sqlglot-based parsing and validation at every injection point (generator, executor). All identifiers quoted, all values parameterized.
3. **Multi-tier model routing** — Four tiers (NONE/LIGHTWEIGHT/STANDARD/PREMIUM) with graceful fallback chain. Works without any API keys in demo mode.
4. **Hybrid retrieval** — Dense (BGE-M3 1024-dim) + sparse (SPLADE) vector search with configurable fusion weight.
5. **Self-learning loop** — Feedback collection, validation, QA pair building, schema enrichment, pattern mining, and batch scheduling. All fully implemented.
6. **883 passing tests** — Comprehensive test coverage across all backend modules (models, repositories, services, API routes, policy layers, inference, learning).
7. **Clean architecture** — FastAPI with proper DI, middleware stack (auth, tenant, rate limiting, logging, CORS, error handling), and clear module boundaries.
8. **Multi-tenant by design** — Row-level security in migrations, tenant middleware, collection-per-tenant in Qdrant, tenant-scoped repositories.
9. **Security-first design** — JWT auth, API key auth, rate limiting, CORS, structured logging, request ID tracing, error handler that doesn't leak details in production.
10. **Demo mode without infrastructure** — Mock clients, demo schema data, dry-run execution — the entire system works end-to-end without PostgreSQL, Redis, or Qdrant.

### 1.5 Top 10 Weaknesses

1. **Critical: In-memory-only state** — Sessions, alerts, user feedback processing — all in-memory. Lost on restart. File-based JSON store for users/tenants was added late and is not scalable.
2. **Pre-existing technical debt** — 168+ Ruff E501 violations (line length), ~50 pre-existing MyPy errors (type annotations), unused imports, ambiguous variable names (`l`).
3. **Mock implementations in production path** — Embedding service falls back to mock when HF token missing. Inference falls back to MockClient. The production path has never been tested against real models.
4. **Frontend is a shell** — Next.js 15 scaffolded, but all pages are stubs with "Coming in Sprint X" content. The chat interface, schema browser, history sidebar, and admin dashboard were built but are functional placeholders. No frontend tests beyond 6 vitest.
5. **No real embeddings** — BGE-M3 mock uses deterministic sparse vectors. The entire retrieval pipeline has never been tested with real embeddings against a real Qdrant instance.
6. **No load testing** — `tests/load/` contains 4 empty directories. No performance baselines exist. No benchmark results.
7. **Connection pool defaults** — `pool_size=5, max_overflow=10` in the executor — completely untuned for production.
8. **Missing production infrastructure** — Helm chart is a template, Terraform is stubs, K8s manifests lack PodDisruptionBudgets and comprehensive network policies. No CD pipeline runs anywhere.
9. **Research spikes not started** — SPIKE-001 (Context Layer Accuracy), SPIKE-002 (Cold-Start Strategy), SPIKE-003 (Model Router Accuracy) are critical for validating architectural assumptions. The architecture may need significant changes based on these results.
10. **Documentation drift** — Implementation Plan references Sprint 0 scope, epic status is inaccurate (many "planned" epics are actually implemented), and the status dashboard contradicts actual code state.

### 1.6 What should be built next?

1. **Replace mock implementations** — Connect real BGE-M3, real LLM inference (vLLM/SGLang), and validate accuracy.
2. **Persistent state stores** — Replace in-memory session/alert/feedback stores with Redis/PostgreSQL-backed implementations.
3. **Frontend MVP** — Complete the chat interface, schema browser, and settings pages with real functionality and E2E tests.
4. **Load testing + performance baselines** — Run benchmarks against Spider 2.0 and BIRD, establish P50/P95/P99 latency targets.
5. **Production infrastructure** — Complete Helm chart, Terraform modules, CD pipeline, and deploy to a staging cluster.
6. **Research spikes** — Validate context layer accuracy, cold-start strategy, and model router before GA.
7. **Enterprise features** — SSO/SAML, SOC 2 audit logging, data residency controls, team management UI.
8. **Security hardening** — Penetration testing, supply chain security (SBOM, signed images), network policies in production.
9. **API documentation** — Complete OpenAPI spec, developer portal, SDK generation.
10. **Multi-region deployment** — Global replication, latency-based routing, disaster recovery.

---

## 2. Overall Scores

| Category | Score | Verdict |
|----------|-------|---------|
| Architecture | 72/100 | PARTIALLY VERIFIED |
| AI System | 68/100 | PARTIALLY VERIFIED |
| Backend | 75/100 | VERIFIED |
| Frontend | 35/100 | PARTIALLY VERIFIED |
| Security | 70/100 | PARTIALLY VERIFIED |
| Database | 65/100 | PARTIALLY VERIFIED |
| DevOps | 30/100 | DOCUMENTATION ONLY |
| Observability | 45/100 | PARTIALLY VERIFIED |
| Documentation | 50/100 | PARTIALLY VERIFIED |
| Code Quality | 60/100 | PARTIALLY VERIFIED |
| Testing | 72/100 | VERIFIED |
| Performance | 15/100 | NOT IMPLEMENTED |
| Scalability | 40/100 | PARTIALLY VERIFIED |
| Maintainability | 55/100 | PARTIALLY VERIFIED |
| Product Readiness | 40/100 | PARTIALLY VERIFIED |
| Enterprise Readiness | 35/100 | PARTIALLY VERIFIED |
| Startup Potential | 60/100 | PARTIALLY VERIFIED |
| Innovation | 55/100 | PARTIALLY VERIFIED |
| Competitive Advantage | 50/100 | PARTIALLY VERIFIED |
| **Overall Engineering** | **55/100** | **CONDITIONAL PASS** |

---

## 3. Verdict: CONDITIONAL PASS

The repository demonstrates solid engineering fundamentals with genuine architectural sophistication in the AI pipeline, security, and multi-tenant design. The 883 passing tests, clean FastAPI architecture, and comprehensive guardrail stack are genuinely impressive.

However, the project is not production-ready. Critical weaknesses in state persistence, mock implementations in the critical path, incomplete frontend, missing load testing, and unvalidated research assumptions prevent a PASS verdict.

**Recommended for:** Private beta with technical design partners, enterprise evaluation under controlled conditions, and continued engineering investment.

**Not ready for:** General Availability, enterprise production deployment, or multi-tenant SaaS launch without 3-6 months of additional engineering work on the identified weaknesses.
