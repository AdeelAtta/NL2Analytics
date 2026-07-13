# Technical Debt Report

**Project:** SchemaIntern
**Date:** 2026-07-11
**Estimated Debt:** ~4-6 weeks to address identified items
**Score:** 45/100 (HIGH DEBT)

---

## Executive Summary

The project has accumulated significant technical debt primarily from architecture drift (collapse of microservices into monolith), empty stub directories, security gaps, and undocumented features. Estimated 4-6 weeks of focused effort to remediate.

---

## Technical Debt Items

### Architecture Debt (2-3 weeks)

| # | Item | Effort | Impact | Priority |
|---|------|--------|--------|----------|
| TD-01 | Query pipeline logic in KE service (should be separate service) | 2 weeks | HIGH | Medium |
| TD-02 | No LangGraph agent orchestration (uses function calls) | 1 week | MEDIUM | Low |
| TD-03 | Missing shared modules (events, clients, middleware) | 3 days | MEDIUM | Medium |
| TD-04 | `schema_intelligence/` naming mismatch with spec | 1 day | LOW | Low |
| TD-05 | 12 empty stub directories | 1 day | LOW | High |

### Security Debt (1-2 weeks)

| # | Item | Effort | Impact | Priority |
|---|------|--------|--------|----------|
| TD-06 | SQL injection in generator.py | 1 day | CRITICAL | Immediate |
| TD-07 | SQL injection in executor.py | 1 day | CRITICAL | Immediate |
| TD-08 | Missing rate limiting | 2 days | HIGH | Immediate |
| TD-09 | JWT hardening (RS256, aud, iss) | 1 day | HIGH | High |
| TD-10 | RBAC implementation | 3 days | HIGH | High |
| TD-11 | Exception info leak | 1 day | HIGH | High |
| TD-12 | Tenant authorization | 2 days | MEDIUM | High |
| TD-13 | Immutable audit chain | 2 days | MEDIUM | Medium |

### Testing Debt (1-2 weeks)

| # | Item | Effort | Impact | Priority |
|---|------|--------|--------|----------|
| TD-14 | No coverage measurement | 1 day | MEDIUM | Medium |
| TD-15 | No migration tests | 2 days | MEDIUM | Medium |
| TD-16 | No security tests | 3 days | HIGH | High |
| TD-17 | No load/performance tests | 3 days | MEDIUM | Low |
| TD-18 | No E2E tests for user journeys | 1 week | HIGH | Medium |

### Documentation Debt (1 week)

| # | Item | Effort | Impact | Priority |
|---|------|--------|--------|----------|
| TD-19 | Undocumented features (Observability, Quality Scorer, PII) | 3 days | MEDIUM | Medium |
| TD-20 | No ADRs for architecture decisions | 1 day | MEDIUM | Medium |
| TD-21 | README out of date with actual structure | 1 day | LOW | Low |
| TD-22 | Missing docstrings on public APIs | 2 days | LOW | Low |

### Infrastructure Debt (2-3 weeks)

| # | Item | Effort | Impact | Priority |
|---|------|--------|--------|----------|
| TD-23 | Dockerfiles reference wrong paths | 1 day | HIGH | High |
| TD-24 | CI/CD pipeline not functional | 2 days | HIGH | High |
| TD-25 | Helm charts are minimal templates | 3 days | MEDIUM | Medium |
| TD-26 | K8s manifests lack probes, PDBs, network policies | 2 days | MEDIUM | Medium |
| TD-27 | Terraform is skeleton only | 3 days | MEDIUM | Low |

---

## Debt Heat Map

```
IMMEDIATE (this sprint)    HIGH (next sprint)      MEDIUM (this month)
─────────────────────    ───────────────────      ──────────────────
TD-06 SQL injection       TD-08 Rate limiting     TD-01 Service split
TD-07 SQL injection       TD-09 JWT hardening     TD-12 Tenant auth
TD-23 Docker paths        TD-10 RBAC              TD-13 Audit chain
                          TD-11 Exception leak     TD-14 Coverage
                          TD-16 Security tests     TD-19 ADRs
                          TD-24 CI/CD             TD-25 Helm
                                                  TD-26 K8s
```

---

## Debt-to-Value Ratio

| Category | Current State | Target State | Debt |
|----------|--------------|-------------|------|
| Architecture | 55% compliant | 90%+ | High |
| Security | 25/100 | 90/100+ | Critical |
| Testing | 52/100 | 85/100+ | Medium |
| Documentation | 60/100 | 85/100+ | Medium |
| Infrastructure | 10/100 | 90/100+ | Critical |
| **Overall** | **40%** | **88%+** | **Very High** |

---

## Recommendations

1. **Fix security debt first** — SQL injection and rate limiting are the highest risk items
2. **Fix infrastructure debt** — Docker paths and CI/CD before any deployment
3. **Document architecture decisions** — Create ADRs for undocumented features
4. **Plan microservices extraction** — Create migration plan for service separation
5. **Consolidate directories** — Clean up 12 empty stub directories
6. **Set up coverage tracking** — Start measuring what's tested vs what's not

---

## Technical Debt Trend

| Month | Debt Level | Notes |
|-------|------------|-------|
| Current | HIGH | 4-6 weeks estimated remediation |
| Target (1 month) | MEDIUM | Security and infrastructure fixed |
| Target (3 months) | LOW | Architecture debt addressed, full test coverage |

---

**Estimated total remediation effort: 4-6 weeks (single engineer)**
