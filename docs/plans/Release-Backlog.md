# Release Backlog

**Generated:** 2026-07-11 | **Source:** docs/reviews/Finding-Validation.md

Only VERIFIED BUG and DOCUMENTATION ISSUE findings are included.

---

## Priority P0 — Security (Blocking Release)

| ID | Finding | Title | Evidence | Severity | Blocking | Related Spec | Related ADR | Existing Epic | Existing Task | Effort | Risk |
|----|---------|-------|----------|----------|----------|-------------|-------------|---------------|---------------|--------|------|
| RB-001 | S-01 | Hardcoded default service token | `ke/api/middleware/auth.py:13`: `"ke_dev_token_2026"` fallback | CRITICAL | Yes | Security-Spec §11.1 | ADR-004 | EP-005 | TASK-032 (auth scaffolded, token fix needed) | S | Low |
| RB-002 | S-04 | Default JWT secret in config | `app/core/config.py:28`: `"change-me-in-production"` | CRITICAL | Yes | Security-Spec §8.1 | — | — | — | S | Low |
| RB-003 | S-05 | SQL injection in rule-based generator | `ke/services/generator.py:224`: f-string filter value interpolation | HIGH | Yes | Security-Spec §4.1 | — | — | — | M | Medium |
| RB-004 | S-06 | SQL injection in executor EXPLAIN | `ke/services/executor.py:62`: f-string EXPLAIN wrapper | HIGH | Yes | Security-Spec §4.1 | — | EP-011 | — | S | Medium |
| RB-005 | S-07 | No rate limiting on any endpoint | Zero rate limiting middleware/decorator found | HIGH | Yes | API-Spec §13, Security-Spec §1.1 D-01 | — | EP-013 | TASK-108 (rate limiting planned for Public API) | M | Medium |
| RB-006 | S-08 | Raw SQL execute endpoint lacks Pydantic model | `ke/api/routes/executor.py:21`: `body: dict[str, Any]` | HIGH | Yes | API-Spec §6, Security-Spec §4 | — | EP-011 | — | S | Low |
| RB-007 | S-09 | Exception details leaked to clients | `app/middleware/error_handler.py:16`: `detail=str(exc)` | HIGH | Yes | Security-Spec §1.1 I-01 | — | — | — | S | Low |
| RB-008 | S-10 | Default DB credentials in source code | `app/core/config.py:20-22`: `schemaintern:schemaintern_dev@localhost` | HIGH | Yes | Security-Spec §9.1 | ADR-012 | — | — | S | Low |
| RB-009 | S-07b | KE API `/docs` publicly accessible | `ke/api/main.py:26`: `/docs` excluded from ServiceAuthMiddleware | MEDIUM | Yes | Security-Spec §11.3 | ADR-004 | EP-005 | TASK-032 | S | Low |
| RB-010 | — | MockClient sync blocking in async context | `ke/services/inference.py:127-134`: `MockClient.generate()` uses sync `re.search` but declared `async` | MEDIUM | No | — | — | — | — | S | Low |
| RB-011 | — | JWT auth dependencies not enforced on routes | `app/auth/dependencies.py:9-19`: `auto_error=False`, defaults to anonymous | HIGH | Yes | Security-Spec §12, API-Spec §3 | — | EP-013 | TASK-106 | M | Medium |

## Priority P1 — Data Integrity

| ID | Finding | Title | Evidence | Severity | Blocking | Related Spec | Related ADR | Existing Epic | Existing Task | Effort | Risk |
|----|---------|-------|----------|----------|----------|-------------|-------------|---------------|---------------|--------|------|
| RB-012 | FK Indexes | Missing indexes on foreign key columns | `backend/alembic/versions/` — no FK index in migration files | MEDIUM | No | Database-Spec §4 | — | — | — | M | Low |
| RB-013 | Migration Tests | No database migration tests | No test files for Alembic migrations | MEDIUM | No | Database-Spec §8 | ADR-013 | — | — | M | Low |

## Priority P2 — Production Readiness (Future Epics)

| ID | Finding | Title | Evidence | Severity | Blocking | Related Spec | Related ADR | Existing Epic | Existing Task | Effort | Risk |
|----|---------|-------|----------|----------|----------|-------------|-------------|---------------|---------------|--------|------|
| RB-017 | — | No container registry configured | CI builds images but no push destination | MEDIUM | No | Deployment-Spec | — | EP-016 | TASK-140 | M | Medium |
| RB-018 | — | No deployment automation (CD) | No CD pipeline or deployment scripts | MEDIUM | No | Deployment-Spec | — | EP-016 | TASK-139 | L | High |

## Priority P3 — Performance

| ID | Finding | Title | Evidence | Severity | Blocking | Related Spec | Related ADR | Existing Epic | Existing Task | Effort | Risk |
|----|---------|-------|----------|----------|----------|-------------|-------------|---------------|---------------|--------|------|
| RB-019 | — | No load testing | `tests/load/` — 4 empty directories | MEDIUM | No | Performance-Budgets | — | EP-017 | — | L | Low |
| RB-020 | — | No performance baselines | No benchmark results documented | LOW | No | Performance-Budgets | — | EP-017 | — | M | Low |
| RB-021 | — | Connection pool settings are defaults | `executor.py:32`: pool_size=5, max_overflow=10 | LOW | No | Database-Spec §6.2 | — | — | — | S | Low |

## Priority P4 — Documentation

| ID | Finding | Title | Evidence | Severity | Blocking | Related Spec | Related ADR | Existing Epic | Existing Task | Effort | Risk |
|----|---------|-------|----------|----------|----------|-------------|-------------|---------------|---------------|--------|------|
| RB-022 | — | README references outdated `src/` paths | README.md references `src/backend/` instead of `backend/` | LOW | No | — | — | — | — | S | Low |
| RB-023 | — | Missing ADRs for undocumented features | OTel, Prometheus, Query Quality Scorer, PII Detection, Ontology Service, Alert Service, Multi-Turn Session | LOW | No | — | — | — | — | M | Low |
| RB-024 | — | No deployment runbooks | No deployment documentation exists | MEDIUM | No | Deployment-Spec | — | EP-016 | — | M | Low |

### RB-022 Status
- **Classification**: ALREADY DONE — README.md uses `backend/` paths; `src/` not found in any version of README.md. No changes needed.
- **Resolution**: Verified current on 2026-07-11. Finding was stale/mischaracterized.

### RB-023 Status
- **Classification**: COMPLETED — ADR-017 (Query Quality Scorer), ADR-018 (PII Detection), ADR-019 (Ontology Service), ADR-020 (Alert Service), ADR-021 (Multi-Turn Session) created.
- **Resolution**: All 5 undocumented features now have ADRs. ADR-016 already covered Observability (OTel + Prometheus).

---

## Execution Order

Items were executed in this order:

1. ✅ **RB-001**: Force KE_API_TOKEN env var, remove hardcoded default
2. ✅ **RB-002**: Generate random JWT secret, require JWT_SECRET env var
3. ✅ **RB-003**: Fix SQL injection in rule-based generator (use sqlglot or parameterization)
4. ✅ **RB-004**: Fix SQL injection in executor EXPLAIN (use sqlglot parse/validate)
5. ✅ **RB-005**: Add rate limiting middleware
6. ✅ **RB-006**: Add Pydantic model for execute endpoint
7. ✅ **RB-007**: Sanitize exception handler — never expose `str(exc)`
8. ✅ **RB-008**: Remove default DB credentials, require env vars
9. ✅ **RB-009**: Disable KE API docs in production mode
10. ✅ **RB-010**: Fix MockClient to be properly async
11. ✅ **RB-012**: Add Alembic migration with FK indexes
12. ✅ **RB-022**: Fix README paths (already correct)
13. ✅ **RB-023**: Add ADRs for undocumented features

### Skipped
- **RB-011**: PARTIALLY CORRECT finding — deferred to EP-013 (Public API) per architecture decision
- **RB-013**: PLANNED finding — requires database snapshot test framework; no action taken
- RB-014 through RB-021: Covered by existing future epics (EP-015, EP-016, EP-017)
- RB-024: Deployment runbooks covered by EP-016

## Release Status (2026-07-11)

### Completed
- RB-001: Hardcoded service token removed — ✅ Done
- RB-002: JWT secret hardened — ✅ Done
- RB-003: SQL injection in generator — ✅ Done
- RB-004: SQL injection in executor — ✅ Done
- RB-005: Rate limiting middleware — ✅ Done
- RB-006: Pydantic model for execute endpoint — ✅ Done
- RB-007: Exception details sanitized — ✅ Done
- RB-008: Default credentials warning — ✅ Done
- RB-009: KE API docs protected — ✅ Done
- RB-010: MockClient sync/async — ✅ Done
- RB-012: FK indexes migration — ✅ Done
- RB-022: README paths — ✅ Already correct
- RB-023: Missing ADRs — ✅ Done (ADR-017 through ADR-021)

### Skipped
- RB-011: JWT auth enforcement — PARTIALLY CORRECT finding; deferred to EP-013 (Public API)
- RB-013: Migration tests — PLANNED finding; requires database snapshot test framework
- RB-014 through RB-021 — Covered by existing future epics (EP-015, EP-016, EP-017)
- RB-024 — Deployment runbooks covered by EP-016

## Legend

| Severity | Meaning |
|----------|---------|
| CRITICAL | Must be fixed before any production release |
| HIGH | Must be fixed before production release |
| MEDIUM | Should be fixed before production release |
| LOW | Can be addressed post-launch |

| Effort | Range |
|--------|-------|
| S | < 2 hours |
| M | 2-8 hours |
| L | 1-3 days |
| XL | 3-10 days |
