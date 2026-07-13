# Release Checklist

**Project:** SchemaIntern
**Date:** 2026-07-11
**Status:** ❌ NOT READY FOR RELEASE

---

## Pre-Release Gates

### Security
- [ ] 🔴 **CRITICAL** Rotate all exposed secrets (HF token, JWT secret, DB passwords)
- [ ] 🔴 **CRITICAL** Remove `.env` from git history
- [ ] 🔴 **CRITICAL** Add `backend/.gitignore` excluding `.env`
- [ ] 🔴 Implement rate limiting on all API endpoints
- [ ] 🔴 Fix SQL injection vectors in `generator.py` and `executor.py`
- [ ] 🔴 Add policy chain enforcement to `/v1/ke/execute`
- [ ] 🔴 Fix error handler to not leak exception details
- [ ] 🔴 Change JWT to RS256 with proper key management
- [ ] 🔴 Validate `aud` and `iss` claims in JWT decode
- [ ] 🟡 Implement RBAC and enforce on all routes
- [ ] 🟡 Add tenant authorization (validate service→tenant mapping)
- [ ] 🟡 Standardize tenant ID extraction to header-only
- [ ] 🟡 Change HTTPBearer to `auto_error=True`
- [ ] 🟡 Path parameter validation (length, format, charset)
- [ ] 🟢 Implement immutable audit log chain
- [ ] 🟢 SAST scanning in CI (semgrep)
- [ ] 🟢 Dependency vulnerability scanning in CI (pip-audit)

### Infrastructure
- [ ] 🔴 Provision production Kubernetes cluster
- [ ] 🔴 Configure DNS and TLS certificates
- [ ] 🔴 Set up container registry with signed images
- [ ] 🔴 Configure database replication and backups
- [ ] 🟡 Set up monitoring stack (Prometheus + Grafana + Loki + Tempo)
- [ ] 🟡 Configure alerting (PagerDuty/OpsGenie)
- [ ] 🟡 Implement blue/green or canary deployment
- [ ] 🟡 Configure auto-scaling (HPA + cluster autoscaler)
- [ ] 🟢 Set up staging environment
- [ ] 🟢 Disaster recovery procedures documented

### CI/CD
- [ ] 🔴 Test and fix GitHub Actions CI workflow
- [ ] 🔴 Docker image build and push to registry
- [ ] 🔴 Automated test execution in CI
- [ ] 🔴 Security scanning in CI (Trivy, semgrep)
- [ ] 🟡 Automated deployment to staging
- [ ] 🟡 Manual approval gate for production
- [ ] 🟡 Rollback automation
- [ ] 🟢 SBOM generation
- [ ] 🟢 Code signing

### Features
- [ ] 🔴 Complete EP-012 Learning Loop
- [ ] 🔴 Complete EP-013 Public API (port 8100)
- [ ] 🔴 Complete EP-014 Frontend (basic query flow)
- [ ] 🟡 Complete EP-015 Multi-Tenant Infrastructure
- [ ] 🟡 Complete EP-016 CI/CD & Observability
- [ ] 🟡 Authentication endpoints (login, register, refresh)
- [ ] 🟡 Database connection management
- [ ] 🟢 Query history and feedback in Public API
- [ ] 🟢 Admin endpoints (usage, team)
- [ ] 🟢 WebSocket API for real-time updates

### Testing
- [ ] 🔴 Load testing at 2x expected peak
- [ ] 🔴 Penetration testing (external firm)
- [ ] 🟡 Integration tests for all API endpoints
- [ ] 🟡 E2E tests for critical user journeys
- [ ] 🟡 Test coverage > 80% (currently not measured)
- [ ] 🟢 All 837 existing tests continue to pass

### Documentation
- [ ] 🟡 README updated with production setup
- [ ] 🟡 Deployment runbooks created
- [ ] 🟡 Incident response runbooks
- [ ] 🟢 API documentation (auto-generated)
- [ ] 🟢 CHANGELOG.md updated

---

## Release Approval Gates

### Gate 1: Feature Complete
- [ ] All P0 epics complete (EP-001 through EP-014)
- [ ] All P0 tasks complete
- [ ] No known critical or high bugs

### Gate 2: Security Approved
- [ ] No critical or high security findings
- [ ] Penetration test passed
- [ ] Dependency scan clean

### Gate 3: Performance Verified
- [ ] Load test passed at 2x peak
- [ ] P95 latency under targets
- [ ] No memory leaks over 24h soak

### Gate 4: Operations Ready
- [ ] Monitoring dashboards available
- [ ] Alerts configured and tested
- [ ] Runbooks published
- [ ] On-call rotation established

### Gate 5: Stakeholder Approval
- [ ] Product owner sign-off
- [ ] Engineering lead sign-off
- [ ] Security lead sign-off

---

## Legend

- 🔴 **Blocking** — Must be resolved before any production release
- 🟡 **Important** — Should be resolved before MVProduction release
- 🟢 **Enhancement** — Can be addressed post-launch

---

## Estimated Timeline

| Phase | Duration | Description |
|-------|----------|-------------|
| Security remediation | 2 weeks | Fix all 🔴 security items |
| Infrastructure provisioning | 2 weeks | K8s, DNS, TLS, monitoring |
| CI/CD implementation | 1 week | Pipeline, builds, deployments |
| Feature completion | 4 weeks | EP-012 through EP-014 |
| Testing & hardening | 3 weeks | Load test, pentest, bug fixes |
| **Total** | **~12 weeks** | |

---

**Current Status: ALL items are blocking. Release not possible.**
