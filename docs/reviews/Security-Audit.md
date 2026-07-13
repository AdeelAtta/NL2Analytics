# Security Audit Report

**Project:** SchemaIntern
**Date:** 2026-07-11
**Risk Level:** CRITICAL
**Overall Score:** 25/100 (F)

---

## Executive Summary

The application has 4 critical, 6 high, 7 medium, and 3 low severity security findings. The most concerning issues are hardcoded secrets in the git repository, lack of rate limiting, SQL injection vectors in production code, and missing authentication/authorization controls. Immediate remediation is required before any production deployment.

---

## Files Reviewed

| File | Purpose |
|------|---------|
| `backend/ke/api/middleware/auth.py` | Service token auth |
| `backend/ke/api/middleware/tenant.py` | Tenant context |
| `backend/app/middleware/cors.py` | CORS configuration |
| `backend/app/middleware/error_handler.py` | Global error handler |
| `backend/app/auth/jwt.py` | JWT token creation/verification |
| `backend/app/auth/dependencies.py` | Auth dependency injection |
| `backend/app/core/config.py` | Settings and defaults |
| `backend/ke/services/generator.py` | SQL generation |
| `backend/ke/services/executor.py` | SQL execution |
| `backend/ke/services/inference.py` | Model inference (MockClient) |
| `backend/ke/services/policy/layers.py` | Guardrail policy layers |
| `backend/ke/api/routes/executor.py` | Direct SQL execution endpoint |
| `backend/.env` | Environment secrets |
| `backend/tests/ke/conftest.py` | Test fixtures with tokens |

---

## Findings

### CRITICAL

#### S-01: Hardcoded Default Service Token
**File:** `backend/ke/api/middleware/auth.py:13`
```
expected = os.environ.get("KE_API_TOKEN", "ke_dev_token_2026")
```
The default token `ke_dev_token_2026` is hardcoded. If `KE_API_TOKEN` env var is not set, any request with this token is authenticated. This string is also hardcoded in 6 test files and is trivially discoverable.

#### S-02: Hugging Face API Token Leaked in Git
**File:** `backend/.env`
```
HF_TOKEN=<HUGGING_FACE_TOKEN>
```
The `.env` file is committed to the repository (confirmed via `git ls-files`). The HF token is a live API credential. **Immediate rotation required.**

#### S-03: No `.gitignore` at Backend Level
**File:** N/A (missing)
No `.gitignore` exists in the `backend/` directory. The root `.gitignore` may not be sufficient to exclude `.env` files in subdirectories.

#### S-04: Default JWT Secret
**File:** `backend/app/core/config.py:28`
```python
jwt_secret: str = "change-me-in-production"
```
Combined with HS256 algorithm, this secret is trivially brute-forceable. The JWT verification also does not validate `aud` or `iss` claims.

---

### HIGH

#### S-05: SQL Injection in Rule-Based Generator
**File:** `backend/ke/services/generator.py:211-251`
Column names, table names, operator strings, and filter values are interpolated into SQL strings via f-strings without escaping. Values originate from `QueryIntent` which stems from user input.

#### S-06: SQL Injection in Executor
**File:** `backend/ke/services/executor.py:62`
```python
explain_sql = f"EXPLAIN (FORMAT JSON) {sql_stripped}"
```
User-provided SQL is f-string interpolated into an EXPLAIN wrapper. The `/v1/ke/execute` endpoint bypasses policy chain entirely.

#### S-07: No Rate Limiting
**Severity: HIGH**
No rate limiting middleware, decorator, or configuration exists anywhere in the codebase. All endpoints are vulnerable to brute-force, credential stuffing, and DoS attacks.

#### S-08: Raw SQL Execution Endpoint Without Policy Chain
**File:** `backend/ke/api/routes/executor.py:21`
```python
async def execute_sql(body: dict[str, Any], ...):
    sql = body.get("sql", "").strip()
```
Accepts arbitrary SQL as `dict[str, Any]` without Pydantic model, no policy chain enforcement, no validation.

#### S-09: Exception Details Leaked to Clients
**File:** `backend/app/middleware/error_handler.py:16`
```python
detail=str(exc),
```
The global exception handler returns raw exception strings to API consumers, leaking stack traces, SQL errors, and file paths.

#### S-10: Default Database Credentials in Config
**File:** `backend/app/core/config.py:20-21`
```python
postgres_dsn: str = "postgresql+asyncpg://schemaintern:schemaintern_dev@localhost:5432/schemaintern"
```
Production database credentials with default password in source code.

---

### MEDIUM

#### S-11: Tenant ID Defaults to "default"
**File:** `backend/ke/api/routes/query.py` (and multiple other routes)
When `X-Tenant-Id` is absent, tenant_id defaults to `"default"`, causing all untentanted requests to share the same namespace.

#### S-12: No Tenant Authorization Check
Service token auth is per-service, not per-tenant. Any service with a valid token can access any tenant's data. No cross-tenant access validation exists.

#### S-13: JWT Auth Silently Downgrades to Anonymous
**File:** `backend/app/auth/dependencies.py`
```python
security = HTTPBearer(auto_error=False)
```
When no auth header is present, the system returns `{"sub": "anonymous", "role": "guest"}` instead of rejecting the request. The `require_role` dependency exists but no routes use it.

#### S-14: JWT Missing Claim Validation
`jwt.decode()` does not validate `aud`, `iss`, or `nbf` claims. This allows token reuse across different services and environments.

#### S-15: Tenant ID Inconsistency
Some routes use `X-Tenant-Id` header, others accept `tenant_id` as query parameter. The query parameter approach is easily manipulated by end users.

#### S-16: CORS Permissive Configuration
```python
allow_methods=["*"],
allow_headers=["*"],
```
Combined with `allow_credentials=True`, this can be dangerous if `cors_origins` is widened.

---

### LOW

#### S-17: Regex-Based SQL Injection Detection
**File:** `backend/ke/services/policy/layers.py`
SQL injection detection uses regex patterns that can be bypassed with encoding tricks (unicode normalization, comment injection).

#### S-18: No Path Parameter Validation
Path parameters (`tenant_id`, `database_id`, `table_id`, `key`) are accepted as raw strings with no validation for format, length, or allowed characters.

#### S-19: Missing Security Tests
No tests exist for:
- SQL injection patterns
- Rate limiting (not implemented)
- CORS misconfiguration
- Tenant isolation boundary violations
- RBAC enforcement
- JWT token edge cases (expired, malformed, algorithm confusion)

---

## OWASP Top 10 Coverage

| Category | Status | Notes |
|----------|--------|-------|
| A01: Broken Access Control | ❌ Missing | No RBAC enforcement on routes |
| A02: Cryptographic Failures | ❌ Missing | Default JWT secret, no aud/iss validation |
| A03: Injection | ⚠️ Partial | Policy chain exists but bypassable |
| A04: Insecure Design | ⚠️ Partial | Threat model exists in spec, not implemented |
| A05: Security Misconfiguration | ❌ Missing | Default creds, hardcoded tokens |
| A06: Vulnerable Components | ❌ Not verified | No dependency scanning in CI |
| A07: Auth Failures | ⚠️ Partial | Service token auth works, JWT auth incomplete |
| A08: Software/Data Integrity | ❌ Missing | No signed images, no SBOM |
| A09: Security Logging Failures | ⚠️ Partial | Audit store exists, immutable chain not implemented |
| A10: SSRF | ❌ Missing | No network policies, no URL allowlist |

---

## Recommendations

| Priority | Action | Owner |
|----------|--------|-------|
| Immediate | Rotate HF token, remove `.env` from git history | Security |
| Immediate | Set `KE_API_TOKEN` env var in all environments | DevOps |
| Immediate | Change JWT secret to strong random value | Backend |
| Immediate | Add `backend/.gitignore` excluding `.env` | Backend |
| Week 1 | Implement rate limiting with Redis | Backend |
| Week 1 | Fix SQL injection in generator.py (use parameterized queries) | Backend |
| Week 1 | Add policy chain to `/v1/ke/execute` endpoint | Backend |
| Week 1 | Fix error handler to not leak exception details | Backend |
| Week 1 | Validate `aud` and `iss` in JWT decode | Backend |
| Week 2 | Implement RBAC middleware and enforce on all routes | Backend |
| Week 2 | Add tenant authorization check (validate service→tenant mapping) | Backend |
| Week 2 | Change `auto_error=True` in HTTPBearer | Backend |
| Week 2 | Standardize tenant ID extraction to header-only | Backend |
| Week 2 | Add path parameter validation | Backend |
| Week 2 | Write security tests for all critical paths | QA |
| Week 3 | Implement immutable audit log chain | Backend |
| Week 3 | Add SAST scanning (semgrep) to CI | DevOps |
| Week 3 | Configure CORS with strict defaults | DevOps |

---

**Risk Level: CRITICAL — Do not deploy to production.**
