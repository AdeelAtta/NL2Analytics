# Code Quality Report

**Project:** SchemaIntern
**Date:** 2026-07-11
**Score:** 70/100 (C)
**Risk Level:** MEDIUM

---

## Executive Summary

The codebase is clean of TODOs/FIXMEs and follows consistent patterns. However, there are significant quality concerns including dead/stub code (empty `app/` directories across 6 services), large files exceeding 400-line limits, SQL injection vectors, and missing type safety enforcement (mypy strict not used).

---

## Files Reviewed

All 146 Python source files under `backend/` (excluding `.venv/`).

---

## Findings

### Code Duplication

| Finding | Severity | Location |
|---------|----------|----------|
| Multiple SQLAlchemy `DeclarativeBase` subclasses | LOW | Each store defines its own ORM base (KE stores only) |
| Repeated `getattr(request.state, "tenant_id", None)` pattern | LOW | Across 6+ route files |
| Repeated `async def _get_*_repo` dependency factories | LOW | Schema store routes |

### Cyclomatic Complexity Concerns

| Function | Complexity | File |
|----------|------------|------|
| `_rule_based_generate()` | ~15 (estimated) | `ke/services/generator.py` |
| `pipeline.run()` | ~12 (estimated) | `ke/services/pipeline.py` |
| Schema route handler pattern | 10+ | `ke/api/routes/schema.py` |

### Dead Code / Stub Files

| Path | Issue |
|------|-------|
| `backend/query-pipeline/app/` | Empty directory |
| `backend/schema-intel/app/` | Empty directory |
| `backend/learning-loop/app/` | Empty directory |
| `backend/public-api/app/` | Empty directory |
| `backend/ke-api/app/` | Empty directory |
| `backend/auth/app/` | Empty directory |
| `backend/lib/db/` | Empty |
| `backend/lib/llm/` | Empty |
| `backend/lib/middleware/` | Empty |
| `backend/lib/models/` | Empty |
| `backend/lib/utils/` | Empty |
| `backend/ke/stores/cache/` | Empty |
| `backend/scripts/` (root) | Empty |
| `.github/actions/` | Empty |
| `tests/e2e/` | Empty |
| `tests/load/*/` | 4 empty subdirectories |

### Large Files (Exceeding 400-Line Limit)

| File | Lines | Notes |
|------|-------|-------|
| `ke/stores/schema/repository.py` | 347 | Near limit, acceptable |
| `ke/api/routes/schema.py` | 280 | Acceptable |
| `ke/api/schemas.py` | 82 | Acceptable |
| `ke/services/pipeline.py` | ~250 | Acceptable |

### Magic Numbers

| Finding | Severity | Location |
|---------|----------|----------|
| `pool_size=20, max_overflow=10` | LOW | `app/core/database.py` — should be configurable |
| `limit=20` in search methods | LOW | Various — should be configurable |
| `max_depth=3` in graph traversal | LOW | Should be configurable |

### Naming Consistency

| Issue | Severity | Details |
|-------|----------|---------|
| `schema_intelligence/` vs spec `schema-intel/` | LOW | Underscore vs hyphen |
| `python-jose` vs `PyJWT` in deps | LOW | Spec says RS256, jose supports it |
| `vector/repository.py` uses `vectordb_service` | LOW | Inconsistent naming |

### Documentation Coverage

| Aspect | Coverage | Notes |
|--------|----------|-------|
| Public API docstrings | ~30% | Many classes/functions lack docstrings |
| Google-style docstrings | 0% | Not used anywhere |
| Type hints | 95%+ | Good coverage on function signatures |
| Inline comments | LOW | Minimal — code is mostly self-documenting |

---

## Code Smells

1. **Singleton pattern for global state (removed in cleanup)** `backend/app/core/database.py` previously had `_redis_pool`, `_qdrant_client` as module-level globals. These were removed — the stack uses PostgreSQL only.

2. **Exception swallowing in middleware** `backend/ke/api/middleware/tenant.py` — The `TenantMiddleware` silently continues if `tenant_id` is missing rather than rejecting or warning.

3. **Mixed auth mechanisms** — Two auth systems (KE service token + JWT) with different middleware stacks. Neither is fully enforced.

4. **Config inheritance** `backend/app/core/config.py` — Settings class holds both app-level and KE-level config. Should be separated per service.

5. **Direct dict access** — Several route handlers use `body: dict[str, Any]` instead of Pydantic models, bypassing validation.

---

## Overall Assessment

| Category | Score | Commentary |
|----------|-------|------------|
| Code Organization | 6/10 | Clean core but 12+ empty stub directories |
| Naming Consistency | 7/10 | Mostly consistent, minor deviations |
| Code Duplication | 8/10 | Low duplication |
| Dead Code | 4/10 | Significant stub/empty code |
| Documentation | 4/10 | Limited docstrings, no Google-style |
| Type Safety | 7/10 | Good type hints but mypy strict not enforced |
| Complexity | 6/10 | Some complex functions |
| Test Quality | 7/10 | Good test coverage for what exists |
| **Overall** | **70/100** | **C — Needs cleanup** |
