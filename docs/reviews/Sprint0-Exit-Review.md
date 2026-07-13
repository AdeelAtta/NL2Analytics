# Sprint 0 Exit Review

**Enterprise Data Intelligence Platform — Engineering Foundation Audit**

| Metadata | Value |
|----------|-------|
| **Reviewer** | Engineering Manager / Principal Software Architect |
| **Date** | 2026-07-10 |
| **Scope** | Sprint 0 — Engineering Foundation (infrastructure only) |
| **Reference Docs** | Engineering-Standards.md, EP-001-Dev-Environment.md, TASK-001 through TASK-008 |
| **Verdict** | **Conditional Pass** (8 issues must be resolved before Sprint 1) |

---

## 1. Repository Structure Audit

### Expected (per Engineering-Standards §2.1)

```
schemaintern/
├── .github/workflows/
├── .github/CODEOWNERS
├── .github/PULL_REQUEST_TEMPLATE.md
├── docs/specifications/
├── docs/epics/
├── docs/agents/
├── docs/tasks/
├── docs/templates/
├── docs/decisions/
├── docs/research/
├── backend/{public-api,ke-api,query-pipeline,schema-intel,learning-loop,auth,lib}/
├── frontend/{app,components,lib,stores,hooks,types,styles}/
├── infra/{docker,k8s,terraform,helm,scripts}/
├── shared/{proto,openapi,types}/
├── tests/{unit,integration,e2e,load,fixtures}/
```

### Actual

| Created | Missing |
|---------|---------|
| All major directories exist | `.github/CODEOWNERS` — not created |
| Backend service stubs (auth, ke-api, query-pipeline, etc.) | `.github/PULL_REQUEST_TEMPLATE.md` — not created |
| Frontend layout matches spec | `backend/lib/` sub-packages are empty (models, middleware, db, llm, utils) |
| Infra directories complete | `tests/load/` sub-directories empty (expected — load testing not in Sprint 0) |
| Tests directories exist | 32 empty directories (expected for sprint 0 stubs) |
| Research spike dirs exist | |

### Findings

| # | Finding | Severity | Impact | Remediation | Owner |
|---|---------|----------|--------|-------------|-------|
| RS-01 | Missing `.github/CODEOWNERS` | Low | PRs won't auto-assign reviewers | Create `CODEOWNERS` mapping service dirs to teams | Infrastructure Agent |
| RS-02 | Missing `PULL_REQUEST_TEMPLATE.md` | Low | Inconsistent PR descriptions | Create from template in docs/templates/ | Infrastructure Agent |

**Verdict**: ✅ PASS (minor omissions acceptable for Sprint 0)

---

## 2. Dependency Audit

### Python (backend/pyproject.toml)

| Dependency | Version | Pinned? | Vulns? |
|-----------|---------|---------|--------|
| fastapi | >=0.115.0 | Range | None known |
| uvicorn[standard] | >=0.32.0 | Range | None known |
| pydantic | >=2.9.0 | Range | None known |
| pydantic-settings | >=2.6.0 | Range | None known |
| dependency-injector | >=4.43.0 | Range | None known |
| structlog | >=24.4.0 | Range | None known |
| asyncpg | >=0.30.0 | Range | None known |
| sqlalchemy[asyncio] | >=2.0.36 | Range | None known |
| alembic | >=1.14.0 | Range | None known |
| python-jose[cryptography] | >=3.3.0 | Range | None known |
| passlib[bcrypt] | >=1.7.4 | Range | None known |
| httpx | >=0.28.0 | Range | None known |
| opentelemetry-api | >=1.28.0 | Range | None known |
| opentelemetry-sdk | >=1.28.0 | Range | None known |
| opentelemetry-instrumentation-fastapi | >=0.49b0 | Range | None known |

### Node.js (frontend/package.json)

| Dependency | Version | Pinned? | Vulns? |
|-----------|---------|---------|--------|
| next | ^15.0.0 | Minor | None known |
| react / react-dom | ^19.0.0 | Minor | None known |
| @tanstack/react-query | ^5.60.0 | Minor | None known |
| zustand | ^5.0.0 | Minor | None known |
| next-auth | ^4.24.0 | Minor | None known |
| next-themes | ^0.4.0 | Minor | None known |
| tailwindcss | ^3.4.0 | Minor | None known |
| 13 Radix UI packages | Various | Minor | None known |

### Findings

| # | Finding | Severity | Impact | Remediation | Owner |
|---|---------|----------|--------|-------------|-------|
| DEP-01 | All Python deps use minimum-version ranges (`>=X.Y`) | Low | Builds may differ across installs | Add `uv.lock` to version control | Backend Agent |
| DEP-02 | `passlib` is deprecated (last release 2022) | Low | No security patches after 2024 | Replace with `bcrypt` directly in Sprint 7 hardening | Backend Agent |
| DEP-03 | No dependency lockfile checked into frontend | Medium | `package-lock.json` exists but CI installs with `npm ci` — correct | Acceptable as-is | — |

**Verdict**: ✅ PASS (acceptable for Sprint 0)

---

## 3. Docker Audit

### Files Reviewed
- `infra/docker/docker-compose.yml` — 6 services (postgres, backend, frontend, prometheus, grafana)
- `infra/docker/docker-compose.db.yml` — 2 services (postgres, pgbouncer)
- `infra/docker/Dockerfile.backend` — Multi-stage (builder → dev → prod)
- `infra/docker/Dockerfile.frontend` — Multi-stage (deps → build → prod)
- `infra/docker/prometheus.yml` — Service discovery configs

### Findings

| # | Finding | Severity | Impact | Remediation | Owner |
|---|---------|----------|--------|-------------|-------|
| DKR-01 | **Backend Docker healthcheck path is wrong** | **CRITICAL** | `HEALTHCHECK CMD curl -f http://localhost:8100/health` will always fail. Actual endpoint is `/api/v1/health/live`. Container will show as unhealthy in Docker/K8s. | Change to `http://localhost:8100/api/v1/health/live` in both `Dockerfile.backend` and `docker-compose.yml` | Infrastructure Agent |
| DKR-02 | **Dockerfile.backend installs dev dependencies in prod stage** | **HIGH** | `uv pip install --no-cache-dir -e ".[dev]"` installs pytest, ruff, mypy, pre-commit in the prod image. Bloats image by ~200MB and exposes dev tools. | Separate dev and prod install targets. `prod` stage should use `.[prod]` or omit `[dev]`. | Infrastructure Agent |
| DKR-03 | **Frontend Dockerfile requires `next.config.ts` `output: "standalone"`** | **HIGH** | Dockerfile copies `.next/standalone` at line 32, but `next.config.ts` is empty (no `output: "standalone"`). Build will succeed in CI but prod stage will have missing files. | Add `output: "standalone"` to `next.config.ts` | Frontend Agent |
| DKR-04 | Dockerfile.frontend builds without `NODE_ENV=production` | Medium | Dev dependencies may be included in the build. Build optimizations may be skipped. | Add `ENV NODE_ENV=production` before `npm run build` | Infrastructure Agent |
| DKR-05 | `docker-compose.db.yml` and main `docker-compose.yml` overlap | Low | Two compose files with different PgBouncer configurations could cause confusion. | Acceptable for Sprint 0. Document which to use for what. | — |

**Verdict**: ❌ **FAIL** — 1 CRITICAL, 2 HIGH issues block production Docker readiness

---

## 4. Backend Audit

### Files Reviewed
- `backend/app/main.py` — App factory
- `backend/app/core/config.py` — Settings via pydantic-settings
- `backend/app/core/database.py` — Async SQLAlchemy engine (Redis/Qdrant managers were removed)
- `backend/app/core/di.py` — dependency-injector container
- `backend/app/core/logging.py` — structlog configuration
- `backend/app/core/health.py` — Health check functions with latency
- `backend/app/middleware/{cors,request_id,logging,error_handler}.py`
- `backend/app/auth/{jwt.py,dependencies.py}` — Auth placeholders
- `backend/app/schemas/health.py` — Pydantic response models
- `backend/app/api/v1/health.py` — Health endpoints

### Findings

| # | Finding | Severity | Impact | Remediation | Owner |
|---|---------|----------|--------|-------------|-------|
| BE-01 | **Duplicate health check implementations** | **HIGH** | `database.py` has `check_db_health()` (returns bool). `health.py` has `check_postgres()` (returns `HealthResult` with latency). Two code paths, two behaviors. `api/v1/health.py` uses `database.py` versions; `health.py` is unused. | Remove `health.py` (dead code). The `database.py` versions are wired to endpoints. Or keep `health.py` and wire it, but don't keep both. | Backend Agent |
| BE-02 | **JWT algorithm is HS256, must be RS256** | **HIGH** | Security-Specification §5.2 mandates RS256. HS256 is symmetric — same key signs and verifies. RS256 uses public/private key pair. | Change `jwt_algorithm` default to `"RS256"` in `config.py`. Requires RSA key pair generation in auth setup. | Backend Agent |
| BE-03 | **Auth placeholders always return anonymous user** | Low | `get_current_user` returns `{"sub": "anonymous", "role": "guest"}` when no JWT provided. Acceptable for Sprint 0 but permits unauthenticated access to all endpoints. | Acceptable for Sprint 0. Document as known gap for Sprint 1. | — |
| BE-04 | `config.py` sets `env_file=".env"` but `backend/.env` doesn't exist | Low | Settings will use defaults. Works for development but may confuse new devs. | Create `backend/.env` from `.env.example` or ensure `make install` copies it. | Backend Agent |
| BE-05 | `di.py` container is minimal — only wires health router | Low | No actual DI usage. Settings and session factory registered but not consumed via DI. | Acceptable for Sprint 0. Expand when real business logic is added in Sprint 1. | — |

**Verdict**: ❌ **FAIL** — 2 HIGH issues (duplicate code, security standard violation)

---

## 5. Frontend Audit

### Files Reviewed
- `frontend/package.json` — Dependencies
- `frontend/next.config.ts` — Next.js configuration
- `frontend/tsconfig.json` — TypeScript strict mode
- `frontend/tailwind.config.ts` — Full theme with CSS variables
- `frontend/styles/globals.css` — Light/dark mode
- `frontend/app/layout.tsx` — Root layout
- `frontend/app/(dashboard)/layout.tsx` — Dashboard shell
- `frontend/components/layout/{Sidebar,TopBar,Providers,AuthGuard}.tsx`
- `frontend/lib/{auth,api,utils}.ts`
- `frontend/stores/app.ts` — Zustand store
- `frontend/app/(dashboard)/{dashboard,query,schema,settings,admin}/page.tsx`
- `frontend/app/auth/{login,logout}/page.tsx`
- 13 shadcn/ui components in `components/ui/`

### Findings

| # | Finding | Severity | Impact | Remediation | Owner |
|---|---------|----------|--------|-------------|-------|
| FE-01 | **`next.config.ts` missing `output: "standalone"`** | **HIGH** | Docker build will fail at prod stage (already flagged as DKR-03). Also needed for K8s readiness. | Add `output: "standalone"` to `next.config.ts` | Frontend Agent |
| FE-02 | **No `test` script in `package.json`** | **HIGH** | `Makefile` targets `test` and `test-frontend` call `npm run test` which fails with `missing script: test`. No frontend testing framework installed. | Add `"test": "echo 'No tests configured yet'"` as placeholder, or install Playwright/ Vitest. | Frontend Agent |
| FE-03 | **`frontend/.env.local` has wrong API URL** | Medium | `NEXT_PUBLIC_API_URL=http://localhost:8080/api/v1` but backend runs on port 8100, base path is `/api/v1`. Mismatch means frontend can't reach backend. | Change to `http://localhost:8100` | Frontend Agent |
| FE-04 | `frontend/.env.local` has placeholder secrets | Low | `NEXTAUTH_SECRET=placeholder-secret-change-in-production`. Acceptable for development. | Ensure `.env.local` is in `.gitignore` | Frontend Agent |
| FE-05 | Auth placeholders use `console.log` for signIn/signOut | Low | 2 ESLint warnings. No actual auth flow. | Acceptable for Sprint 0. Replace with real auth in Sprint 1. | — |

**Verdict**: ❌ **FAIL** — 2 HIGH issues (no test script breaks Makefile, standalone mode missing breaks Docker)

---

## 6. Database Audit

### Files Reviewed
- `backend/alembic/alembic.ini` — Migration config
- `backend/alembic/env.py` — Async migration support
- `backend/alembic/script.py.mako` — Template
- `backend/app/core/database.py` — Connection management
- `backend/scripts/seed.py` — Seed framework
- `backend/scripts/migrate.py` — Migration wrapper
- `infra/docker/postgres-init/01-extensions.sql` — UUID, pg_trgm, pg_stat_statements
- `infra/docker/postgres-init/02-create-schemas.sql` — ke_db, audit, metrics schemas

### Findings

| # | Finding | Severity | Impact | Remediation | Owner |
|---|---------|----------|--------|-------------|-------|
| DB-01 | **No initial Alembic migration exists** | **HIGH** | `alembic upgrade head` will succeed but produce no tables. Developers will write migrations from scratch, possibly inconsistently. | Create initial empty migration with `alembic revision --autogenerate -m "initial"` (will be empty but establishes the baseline). | Database Agent |
| DB-02 | `alembic.ini` has hardcoded DSN (line 4) | Low | env.py overrides this with `get_settings()`, so it's harmless. But the hardcoded value could confuse. | Set `sqlalchemy.url =` to empty or comment out in `alembic.ini` to avoid confusion. | Database Agent |
| DB-03 | Seed script is an empty framework | Low | `seed.py` exists but does nothing. Acceptable for Sprint 0. | Expand in Sprint 1 when actual seed data is needed. | — |

**Verdict**: ✅ CONDITIONAL PASS (resolve DB-01 before Sprint 1)

---

## 7. Infrastructure Audit

### Files Reviewed
- `.devcontainer/devcontainer.json` — Dev container
- `infra/scripts/{setup,docker-build,docker-push}.sh`

### Findings

| # | Finding | Severity | Impact | Remediation | Owner |
|---|---------|----------|--------|-------------|-------|
| INF-01 | Terraform stubs reference `terraform { backend "s3" {} }` but bucket name is placeholder | Low | Would fail on `terraform init`. Acceptable — stubs need real values per environment. | Document required variables. Not a Sprint 0 blocker. | — |
| INF-02 | K8s deployment has `image: upl/backend:latest` — no tag strategy | Low | `latest` is anti-pattern for production. Acceptable for Sprint 0. | Replace with semantic versioning or Git SHA in Sprint 7 hardening. | — |
| INF-03 | Helm chart uses `upl/backend` image reference | Low | Same as INF-02, acceptable for Sprint 0. | — | — |
| INF-04 | No ArgoCD config yet | Low | ADR-014 specifies GitOps with ArgoCD. Not in Sprint 0 scope. | Sprint 7 production hardening. | — |

**Verdict**: ✅ PASS (all stubs acceptable for Sprint 0)

---

## 8. Security Audit

### Files Reviewed
- `backend/app/auth/{jwt.py,dependencies.py}` — Auth placeholders
- `backend/app/middleware/cors.py` — CORS config
- `backend/app/middleware/error_handler.py` — Error handling
- `backend/app/core/config.py` — Secrets
- `.env.example` — Template env

### Findings

| # | Finding | Severity | Impact | Remediation | Owner |
|---|---------|----------|--------|-------------|-------|
| SEC-01 | **JWT uses HS256 (symmetric) instead of RS256 (asymmetric)** | **HIGH** | Security-Specification §5.2 mandates RS256. HS256 means the same secret both signs and verifies tokens. If the secret is leaked, tokens can be forged. Production would require key rotation ceremony. | Change default to `"RS256"`, document key generation in development guide. | Backend Agent |
| SEC-02 | CORS allows all origins in theory (`allow_origins=origins`) but origins list is limited | Low | Acceptable for Sprint 0. Production should restrict to known domains. | Track in hardening checklist. | — |
| SEC-03 | Global exception handler exposes `detail=str(exc)` | Medium | Internal error details (file paths, SQL queries, stack traces) may leak to clients in 500 responses. | Log full exception, return generic message. | Backend Agent |
| SEC-04 | No rate limiting configured | Low | API-Specification §13 specifies rate limiting. Acceptable for Sprint 0 since no public endpoint yet. | Implement in Sprint 1 when public API is built. | — |

**Verdict**: ❌ **FAIL** — 1 HIGH security standard violation (HS256 vs RS256)

---

## 9. Observability Audit

### Files Reviewed
- `infra/docker/prometheus.yml` — Scrape config
- `backend/app/core/logging.py` — structlog config
- `backend/app/middleware/logging.py` — Request logging middleware
- `backend/app/middleware/request_id.py` — Request ID injection

### Findings

| # | Finding | Severity | Impact | Remediation | Owner |
|---|---------|----------|--------|-------------|-------|
| OBS-01 | Prometheus scrape config references services (postgres exporter) not deployed in main docker-compose | Low | Prometheus will log `target not found` for those exporters. Not a Sprint 0 blocker. | Add exporter sidecars or remove from scrape config until Sprint 7. | Infrastructure Agent |
| OBS-02 | Grafana is deployed with no dashboards or datasources | Low | Empty shell. No pre-configured dashboards for RED metrics. | Add dashboards as JSON in Sprint 7. Acceptable for Sprint 0. | — |
| OBS-03 | OpenTelemetry is configured in dependencies but not wired into app | Medium | `opentelemetry-instrumentation-fastapi` is a dependency but not used in `create_app()`. No traces are being exported. | Wire OTel instrumentation into app factory in Sprint 1. | Backend Agent |
| OBS-04 | Structured logging works but no log aggregation configured | Low | Logs go to stdout. Production needs Loki/Elasticsearch. | Sprint 7 hardening. | — |

**Verdict**: ✅ CONDITIONAL PASS (acceptable for Sprint 0, OBS-03 should be tracked)

---

## 10. CI/CD Audit

### Files Reviewed
- `.github/workflows/ci.yml` — 6 jobs: lint, typecheck, test, build, security, coverage

### Findings

| # | Finding | Severity | Impact | Remediation | Owner |
|---|---------|----------|--------|-------------|-------|
| CI-01 | **Lint job doesn't run frontend ESLint** | **HIGH** | Frontend code changes won't be linted in CI. TypeScript errors may slip through. | Add `npx eslint frontend/ --ext .ts,.tsx` step to lint job. | Infrastructure Agent |
| CI-02 | **CI uses `uv pip install --system -e "backend/[dev]"`** | **HIGH** | This installs into the system Python, which could conflict with GitHub Actions runners. Also installs dev dependencies for all jobs unnecessarily. | Use `uv sync --no-dev` for non-test jobs, or set up proper virtual environment. | Infrastructure Agent |
| CI-03 | Test job requires Postgres services but tests don't use them | Medium | CI service containers run for tests that don't need them. Wastes ~30s per CI run. Tests skip gracefully but services add cost. | Split unit and integration tests. Move integration tests to separate job with services. | QA Agent |
| CI-04 | Build job uses Docker cache from GitHub Actions but no cache key invalidation | Low | Cache may become stale. Acceptable for Sprint 0. | Fine-tune in Sprint 7. | — |
| CI-05 | Security job may fail due to Trivy/npm audit findings in dependencies | Medium | `exit-code: 1` on Trivy means any finding blocks CI. Could cause frequent false positives. | Set `exit-code: 0` initially, fix findings iteratively. | Infrastructure Agent |

**Verdict**: ❌ **FAIL** — 2 HIGH issues (missing frontend lint, wrong pip install method)

---

## 11. Testing Audit

### Test Files

| Test File | Type | Status |
|-----------|------|--------|
| `backend/tests/test_health.py` (3 tests) | Unit | ✅ PASS |
| `backend/tests/test_config.py` (3 tests) | Unit | ✅ PASS |
| `backend/tests/conftest.py` | Fixtures | ✅ Works |
| `tests/unit/test_config.py` (6 tests) | Unit | ✅ PASS |
| `tests/unit/test_imports.py` (9 tests) | Unit | ✅ PASS |
| `tests/integration/test_db_connection.py` (3 tests) | Integration | ⏭️ Skipped (no DB) |

### Findings

| # | Finding | Severity | Impact | Remediation | Owner |
|---|---------|----------|--------|-------------|-------|
| TST-01 | **Root-level `tests/unit/test_config.py` tests a different `Settings` class** | **HIGH** | `TestSettings` uses `SCHEMAINTERN__` prefix and different field names than the actual `Settings` in `backend/app/core/config.py`. These tests pass but validate the wrong configuration model. | Either remove root-level tests (move integration to backend/tests/) or align them with the real `Settings` class. | QA Agent |
| TST-02 | **No frontend tests** | **HIGH** | `package.json` has no `test` script. No Jest/Vitest/Playwright configured. Frontend has no test coverage at all. | Install Vitest + React Testing Library. Add at least smoke test for layout. | Frontend Agent |
| TST-03 | Test coverage is 0% for meaningful code | Medium | Only health endpoint tests exist. No tests for middleware, auth, config edge cases. | Acceptable for Sprint 0. Coverage targets for Sprint 1. | — |
| TST-04 | Integration tests skip silently with no CI warning | Low | `pytest -m "not integration"` would need to be used, but currently all tests run without markers. | Add `integration` marker to integration tests. | QA Agent |

**Verdict**: ❌ **FAIL** — 2 HIGH issues (wrong test config, no frontend tests)

---

## 12. Documentation Audit

### Files Reviewed
- `README.md` — Project overview and quick start
- `docs/development-guide.md` — Setup and coding guide
- `docs/architecture-index.md` — Doc mapping
- `docs/troubleshooting.md` — Common issues
- `docs/contributing.md` — PR process
- `TODO.md` — Sprint tracking
- `docs/progress/status-dashboard.md` — Progress tracking

### Findings

| # | Finding | Severity | Impact | Remediation | Owner |
|---|---------|----------|--------|-------------|-------|
| DOC-01 | `README.md` quick start references `make dev` but `make dev` forks backend + frontend processes without easy cleanup | Low | Running `make dev` leaves background processes. No `make stop` target. | Add `make stop` to kill background processes. | Integration Agent |
| DOC-02 | `docs/development-guide.md` references `npm run test` for frontend but no test script exists | Medium | Devs following the guide will hit an error. (Same root cause as TST-02.) | Fix when test script is added. | Integration Agent |
| DOC-03 | No `.env` file in `backend/` — dev guide should instruct `cp .env.example backend/.env` | Low | Developers may not set up env correctly on first try. | Add explicit copy command to dev guide. | Integration Agent |

**Verdict**: ✅ CONDITIONAL PASS (minor gaps, track alongside fixes)

---

## 13. Performance Baseline

No performance baseline was established in Sprint 0. This is acceptable — Sprint 0 is infrastructure only.

### Recommendations
- Establish request latency baseline before Sprint 1
- Record `pytest --durations=10` output as baseline
- Measure Docker image sizes:
  - Backend prod image: ~500MB estimated (includes dev deps — see DKR-02)
  - Frontend prod image: ~150MB estimated
- First-load JS: 102kB shared, pages 103-111kB (acceptable for MVP)

---

## 14. Code Quality Metrics

| Metric | Backend | Frontend |
|--------|---------|---------|
| Total files | 35 Python files | 35 TypeScript/TSX files |
| Lines of code | ~450 | ~850 |
| Ruff violations | 0 | N/A |
| Mypy violations | 0 | N/A |
| ESLint errors | N/A | 0 |
| ESLint warnings | N/A | 2 (console.log) |
| Test count | 18 (6 backend + 12 root) | 0 |
| Test coverage | ~15% (only health/config) | 0% |
| Docker build | 🔴 HEALTHCHECK broken | 🔴 standalone mode missing |

---

## 15. Technical Debt

| Debt Item | Type | Estimated Effort | Sprint |
|-----------|------|-----------------|--------|
| Duplicate health check code (database.py vs health.py) | Redundancy | 15 min | Sprint 0 fix |
| HS256 → RS256 migration | Security | 30 min | Sprint 0 fix |
| 32 empty directories | Structure | 0 (expected) | — |
| No lockfile for Python deps | Reproducibility | 0 (uv.lock exists) | — |
| Dependency ranges not pinned | Reproducibility | 30 min | Sprint 7 |
| Root-level tests test wrong Settings class | Wrong code | 15 min | Sprint 0 fix |
| `Dockerfile.backend` installs dev deps in prod | Bloat/security | 20 min | Sprint 0 fix |

---

## 16. Missing Items

| Item | Expected In | Status | Priority |
|------|------------|--------|----------|
| `.github/CODEOWNERS` | Engineering-Standards §2.1 | ❌ Missing | Low |
| `.github/PULL_REQUEST_TEMPLATE.md` | Engineering-Standards §2.1 | ❌ Missing | Low |
| Frontend test framework | Sprint 0 spec | ❌ Missing | **High** |
| Initial Alembic migration | EP-001 | ❌ Missing | Medium |
| `.gitignore` entry for `frontend/.next/` | Standard | ✅ Present | — |
| Production Docker Compose | Intent (Sprint 7) | ❌ Not expected | — |
| Grafana dashboards | Observability-Spec | ❌ Sprint 7 | — |

---

## 17. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| HS256 JWT secret leaked before RS256 migration | Low | Critical — token forgery | Fix in Sprint 0 before Sprint 1 starts |
| Docker image healthcheck fails silently | High | Medium — containers marked unhealthy, K8s restarts | Fix healthcheck URL |
| Frontend can't reach backend (port mismatch) | High | Medium — devs see blank pages | Fix `.env.local` port |
| Root-level tests give false confidence | Medium | Low — 6 tests pass but test wrong model | Remove or fix before Sprint 1 |
| OTel not wired means no traces from Sprint 1 | Medium | High — can't debug pipeline latency | Add OTel instrumentation before Sprint 1 |

---

## 18. Recommendations

### Required Before Sprint 1 (Blocker)

| # | Item | References |
|---|------|-----------|
| R1 | Fix Docker healthcheck path: `/health` → `/api/v1/health/live` | DKR-01 |
| R2 | Fix `Dockerfile.backend` prod stage: install without `[dev]` | DKR-02 |
| R3 | Add `output: "standalone"` to `next.config.ts` | DKR-03, FE-01 |
| R4 | Remove duplicate `health.py` or consolidate with `database.py` | BE-01 |
| R5 | Change JWT algorithm from HS256 to RS256 | BE-02, SEC-01 |
| R6 | Fix or remove root-level tests that test wrong Settings class | TST-01 |
| R7 | Add frontend lint step to CI lint job | CI-01 |
| R8 | Add placeholder `test` script to `frontend/package.json` | FE-02 |

### Highly Recommended (Before Sprint 3)

| # | Item | References |
|---|------|-----------|
| H1 | Wire OpenTelemetry instrumentation into app factory | OBS-03 |
| H2 | Create initial Alembic migration | DB-01 |
| H3 | Add frontend test framework (Vitest + RTL) | TST-02 |
| H4 | Install Playwright for E2E tests | Engineering-Standards §5 |

---

## 19. Go / No-Go Recommendation

### Count of Findings by Severity

| Severity | Count |
|----------|-------|
| 🔴 CRITICAL | 1 |
| 🟠 HIGH | 12 |
| 🟡 MEDIUM | 7 |
| 🔵 LOW | 14 |

### Verdict

**CONDITIONAL PASS — 8 blockers must be resolved before Sprint 1 begins.**

Sprint 0 produced a solid foundation. The directory structure, backend app factory, frontend shell, Docker orchestration, CI pipeline, and documentation are structurally sound. However, 8 issues (1 CRITICAL, 7 HIGH) prevent declaring Sprint 0 fully complete:

1. Docker healthcheck path is wrong → service health monitoring broken
2. Dev dependencies in prod Docker image → security + bloat
3. `next.config.ts` missing standalone mode → Docker frontend build broken
4. Duplicate health check code → maintenance burden
5. HS256 instead of RS256 → security standard violation
6. Root-level tests test wrong model → false confidence
7. CI doesn't lint frontend → quality gap
8. No frontend test script → `make test` broken

**Estimated fix time**: ~2-3 hours across all 8 items.

Once these 8 items are resolved, Sprint 0 passes and Sprint 1 (Knowledge Engine) may proceed.

---

*End of Sprint 0 Exit Review*
