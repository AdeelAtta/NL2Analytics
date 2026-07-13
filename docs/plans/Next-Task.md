# Next Task — Execution Plan

**Generated**: 2026-07-10 | **Based on**: Architecture v1.0 (frozen) | **Phase**: 3.5 → 4 Transition

---

## 1. Current State Audit

### What exists (on disk)
- Repository structure per Implementation-Plan.md §4
- Python tooling: `pyproject.toml`, ruff, mypy, pytest configured
- Backend foundation: FastAPI app factory, config, DI, structlog, health endpoints, middleware
- Frontend foundation: Next.js 15 + TypeScript + Tailwind + shadcn/ui, 10 pages
- Database foundation: Alembic migrations, async SQLAlchemy (Redis/Qdrant managers were removed)
- Docker Compose: 6 services (postgres, backend, frontend, prometheus, grafana)
- Dockerfiles: Multi-stage for backend + frontend
- CI/CD: `.github/workflows/ci.yml` — 6 jobs
- Terraform stubs, K8s manifests, Helm chart, dev container
- Pre-commit hooks (ruff, mypy, trailing-whitespace, commitizen)
- Makefile: 18 targets
- Prometheus + Grafana configs
- All 20 specification docs, 17 epic files, 12 task files, 7 agent specs

### What is missing or broken
| Issue | Severity | Details |
|-------|----------|---------|
| No git commits | HIGH | `.git/` exists but zero commits — Sprint 0 work unversioned |
| EP-001 task statuses all `backlog` | HIGH | ~7/8 tasks implemented but tracking never updated |
| TASK-008 (Shared Models) not done | HIGH | `backend/lib/models/` empty; no `backend/shared/`; blocks EP-002 |
| `make install` broken on Windows | MEDIUM | Git Bash path issue with `cd backend && uv sync` |
| Directory naming drift | LOW | `ke-api/` vs specified `ke/`, `schema-intel/` vs `schema-intelligence/` |
| Research spikes not started | MEDIUM | `spikes/` and `research/` dirs don't exist |
| Missing TASK-008 `.md` file | LOW | No task document for shared models |

---

## 2. Dependency Graph (Critical Path)

```
EP-001 ──TASK-008──▶ EP-002 ──TASK-009──▶ TASK-010 ──▶ TASK-011 ──▶ EP-004, EP-005, EP-006, EP-010
                        │
                        └──▶ EP-003 (parallel, depends only on EP-001)
                        └──▶ EP-005 (depends EP-002 + EP-003)
                        └──▶ EP-006 (depends EP-002 + EP-003)
                        └──▶ EP-010 (depends EP-002)
                              └──▶ EP-011 ──▶ EP-012, EP-013
                                                 └──▶ EP-014
EP-001 ──▶ EP-015 (parallel track, K8s infra)
EP-001 ──▶ EP-016 (parallel track, CI/CD)
(None) ──▶ EP-017 (research, no deps, can start immediately)
```

**Critical insight**: The entire downstream chain (EP-002 through EP-014) is blocked on **TASK-008** within EP-001.

---

## 3. Immediate Actions (before implementation)

These corrective actions must be completed first:

| # | Action | Rationale |
|---|--------|-----------|
| 1 | **Commit Sprint 0 work to git** | Prevent work loss; enables status tracking per commit |
| 2 | **Update EP-001 task 1-7 statuses to `done`** | Reflect actual state; unblock dashboard tracking |
| 3 | **Create TASK-008-Setup-Shared-Models.md** | Missing task document; needed before implementation |

---

## 4. Recommended Next Task: TASK-008 — Setup Shared Models Package

### Why this is next
- **Only remaining EP-001 task** — all other Sprint 0 work is structurally complete
- **Blocks EP-002 (Schema Store)** — TASK-009 depends on TASK-008
- **Blocks all downstream epics** — EP-002 is a transitive dependency for EP-004 through EP-014
- **Architecture v1.0 is frozen** — no decision needed, just execute the spec

### What it must produce
- Python package `backend/shared/models/` with `__init__.py`
- Base Pydantic v2 models: `BaseSchema`, `TimestampMixin`, `TenantScopedModel`, `APIResponse`, `PaginationParams`
- No business logic — just shared base classes and types
- Tests validating base model behavior

### Execution steps
1. Create `backend/shared/__init__.py`, `backend/shared/models/__init__.py`
2. Define base models per Database-Specification.md and KnowledgeEngine-Specification.md
3. Ensure `uv sync` resolves the package (add to `pyproject.toml` if needed)
4. Write unit tests for base model validation
5. Run `make lint && make typecheck && make test-backend` to verify
6. Update EP-001 task table: set TASK-008 to `done`
7. Update EP-001 epic status to `done`
8. Commit

### Dependencies satisfied by
- TASK-001 (structure exists)
- TASK-002 (Python tooling works: `uv run pytest`, `ruff`, `mypy` all pass)

---

## 5. Next After TASK-008

| Order | Task | Epic | Agent | Notes |
|-------|------|------|-------|-------|
| 1 | TASK-009 — Define Schema Store data models | EP-002 | KE Agent | First EP-002 task; P0 |
| 2 | TASK-016 — Setup Qdrant client (removed — vector search removed from scope) | EP-003 | KE Agent | Parallel with EP-002 work |
| 3 | SPIKE-001 — Context Layer Accuracy | EP-017 | Research | Must complete before EP-007 |
| 4 | SPIKE-002 — Cold-Start Strategy | EP-017 | Research | Must complete before EP-007 |
| 5 | SPIKE-003 — Model Router Accuracy | EP-017 | Research | Must complete before EP-008 |
| 6 | TASK-010 — Alembic migration for schema store | EP-002 | KE Agent | After TASK-009 |
| 7 | TASK-029 — Scaffold KE API | EP-005 | KE Agent | After EP-002 + EP-003 |
| 8 | TASK-043 — DB connector interface | EP-006 | Schema Intel | After TASK-008 |

---

## 6. Parallelism Opportunities (post TASK-008)

Once TASK-008 is done, four tracks can run in parallel:

| Track | Epics | Agent | Notes |
|-------|-------|-------|-------|
| Schema Store | EP-002 → EP-004 | KE Agent | Sequential within track |
| Vector Index | EP-003 | KE Agent | Independent of EP-002 |
| Research | EP-017 | Research Agent | No deps on anything |
| Infra | EP-015, EP-016 | Infra Agent | Independent of KE work |

**Constraint**: EP-005 (KE API) must wait for both EP-002 and EP-003.

---

## 7. Immediate Blockers

| Blocker | Affects | Resolution |
|---------|---------|------------|
| TASK-008 not done | EP-002 through EP-014 | Complete TASK-008 next |
| Zero git commits | All work | `git add && git commit` after TASK-008 |
| EP-001 statuses stale | Dashboard accuracy | Update task/epic statuses |
| Makefile Windows issue | Developer UX | Fix `cd backend && uv sync` shell escaping |
