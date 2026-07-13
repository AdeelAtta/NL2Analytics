# Repository Health Report

**Project:** SchemaIntern
**Date:** 2026-07-11
**Status:** ⚠️ ABNORMALITIES FOUND
**Score:** 55/100

---

## Executive Summary

The repository has structural issues including duplicate directory conventions, empty stubs, broken Docker references, missing `.gitignore`, and committed secrets. While the core `backend/ke/` code is well-organized, the surrounding infrastructure and documentation have significant health problems.

---

## Findings

### Duplicate Folders / Modules

| Finding | Severity | Details |
|---------|----------|---------|
| `backend/schema-intel/` (empty) vs `backend/schema_intelligence/` (populated) | HIGH | Two directories for same purpose, one empty stub |
| `backend/learning-loop/` (empty) vs no implementation | MEDIUM | Stub directory with no implementation |
| `backend/public-api/` (empty) vs `backend/app/` (actual API) | MEDIUM | Stub directory with no implementation |
| `backend/ke-api/` (empty) vs `backend/ke/` (actual KE) | MEDIUM | Stub directory |
| `backend/query-pipeline/` (empty) vs `backend/ke/services/` (actual logic) | MEDIUM | Logic lives in wrong place |
| `scripts/` (root, empty) vs `backend/scripts/` (populated) | LOW | Two scripts directories |
| `tests/` (root, 3 files) vs `backend/tests/` (42 files) | LOW | Test directory split across two locations |

### Empty / Stub Directories (12 total)

| Directory | Full Path |
|-----------|-----------|
| `schema-intel/app/` | `backend/schema-intel/app/` |
| `query-pipeline/app/` | `backend/query-pipeline/app/` |
| `learning-loop/app/` | `backend/learning-loop/app/` |
| `public-api/app/` | `backend/public-api/app/` |
| `ke-api/app/` | `backend/ke-api/app/` |
| `auth/app/` | `backend/auth/app/` |
| `lib/db/` | `backend/lib/db/` |
| `lib/llm/` | `backend/lib/llm/` |
| `lib/middleware/` | `backend/lib/middleware/` |
| `lib/models/` | `backend/lib/models/` |
| `lib/utils/` | `backend/lib/utils/` |
| `ke/stores/cache/` | `backend/ke/stores/cache/` |

### Broken References

| Reference | Location | Issue |
|-----------|----------|-------|
| Dockerfile references `src/backend/` | `infra/docker/Dockerfile.backend` | Path does not exist — actual code is in `backend/` |
| Docker Compose references `ke-api` service | `infra/docker/docker-compose.yml` | Service definition references missing Dockerfile |
| Makefile `build-backend` target | `Makefile` | References Dockerfile that may not match structure |
| README references `src/` paths | `README.md` | Code is at `backend/` not `src/backend/` |
| README references port 8100 (public-api) | `README.md` | Public API not implemented |
| Implementation Plan references `src/` paths | `docs/Implementation-Plan.md` | Code structure doesn't match |

### Config Duplication

| Config | Location 1 | Location 2 | Consistency |
|--------|-----------|------------|-------------|
| pyproject.toml | root | `backend/` | Both exist, different content |
| pytest config | root `pyproject.toml` | `backend/pyproject.toml` | Overlapping settings |
| alembic.ini | `backend/` | `backend/alembic/` | Duplicate files |

### `.gitignore` Issues

| Problem | Details |
|---------|---------|
| No `.gitignore` in `backend/` | `.env` file committed to git |
| `.env` tracked | `backend/.env` contains live HF auth token |
| Root `.gitignore` may not cover subdirectory `.env` | Unclear coverage |

### Unused Assets

| Asset | Path | Notes |
|-------|------|-------|
| Empty stub directories | 12 locations | No files, no purpose |
| `.github/actions/` | Empty | No custom actions |
| `tests/load/*/` | 4 empty directories | Load testing tools not used |
| `tests/e2e/` | Empty | No E2E tests |
| `backend/infra/` references | Various | Infrastructure files may be stale |

### Broken Links

| Link | Source | Issue |
|------|--------|-------|
| `docs/specifications/` cross-references | Multiple spec files | Links point to sibling files that may not exist |
| `System-Architecture.md` | `docs/Implementation-Plan.md` | File exists, cross-reference OK |
| `API-Design.md` | `docs/Implementation-Plan.md` | File exists |
| `Component-Design.md` | `docs/Implementation-Plan.md` | File exists |

### Dependency Conflicts / Issues

| Dependency | Version | Issue |
|-----------|---------|-------|
| `openai >= 1.55.0` | 1.55.0 | Pinned to exact version (pip freeze output `=1.55.0`) but spec says `>=` |
| `python-jose[cryptography]` | — | Used for JWT but spec says RS256; library supports it |
| `sqlglot` | latest | Used for DDL parsing and AST validation |
| `passlib[bcrypt]` | — | Listed but not used in any source file |

### Broken Imports

| Import | File | Issue |
|--------|------|-------|
| Imports from `.venv` | Various | Works in dev, unclear in prod |
| Cross-service imports | `ke/services/` | No separation of concerns when extracted to microservice |

---

## Recommendations

| Priority | Action |
|----------|--------|
| HIGH | Remove `backend/.env` from git, add `.gitignore` |
| HIGH | Resolve duplicate directory issue (pick one convention) |
| HIGH | Fix Dockerfile paths to match actual structure |
| HIGH | Clean up 12 empty stub directories |
| MEDIUM | Consolidate test directory to single location |
| MEDIUM | Fix README to reflect actual project structure |
| MEDIUM | Consolidate duplicate config files |
| LOW | Remove or implement empty stub modules |
| LOW | Fix cross-reference links in documentation |

---

## Repository Health Scorecard

| Category | Score | Notes |
|----------|-------|-------|
| Directory Structure | 4/10 | Duplicate directories, empty stubs |
| Configuration | 5/10 | Duplicate configs, missing gitignore |
| Dependencies | 7/10 | Reasonable, unused passlib |
| Imports | 6/10 | Work in current layout |
| References | 4/10 | Docker, README, docs out of sync |
| Assets | 3/10 | 12+ empty/stale directories |
| **Overall** | **55/100** | |
