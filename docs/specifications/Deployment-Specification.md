# Deployment Specification

**Enterprise Data Intelligence Platform — Production Deployment Strategy**

| Metadata | Value |
|----------|-------|
| **Author** | Principal Platform Engineer |
| **Date** | 2026-07-10 |
| **Status** | Approved |
| **Version** | 1.0 |
| **Architecture Reference** | System-Architecture.md §7, Deployment-Architecture.md, Architecture-Review.md §11 |
| **Cross-References** | Infrastructure-Specification.md, Engineering-Standards.md §7-8, Security-Specification.md §9, Database-Specification.md §11, Performance-Specification.md §10 |

---

## Table of Contents

1. [Deployment Philosophy](#1-deployment-philosophy)
2. [Local Development](#2-local-development)
3. [Docker Build Strategy](#3-docker-build-strategy)
4. [Dev Containers](#4-dev-containers)
5. [CI/CD Pipeline Architecture](#5-cicd-pipeline-architecture)
6. [Environment Strategy](#6-environment-strategy)
7. [Environment Promotion](#7-environment-promotion)
8. [Blue/Green Deployment](#8-bluegreen-deployment)
9. [Canary Deployment](#9-canary-deployment)
10. [Rolling Updates](#10-rolling-updates)
11. [Rollback Strategy](#11-rollback-strategy)
12. [Secrets Management Operations](#12-secrets-management-operations)
13. [Configuration Management](#13-configuration-management)
14. [Database Migration Operations](#14-database-migration-operations)
15. [Multi-Region Deployment](#15-multi-region-deployment)
16. [Disaster Recovery Procedures](#16-disaster-recovery-procedures)
17. [High Availability Operations](#17-high-availability-operations)
18. [GPU Deployment and Scheduling](#18-gpu-deployment-and-scheduling)
19. [AMD ROCm Deployment Procedures](#19-amd-rocm-deployment-procedures)
20. [NVIDIA Deployment](#20-nvidia-deployment)
21. [Enterprise On-Prem Deployment](#21-enterprise-on-prem-deployment)
22. [Monitoring Integration](#22-monitoring-integration)
23. [Cost Optimization](#23-cost-optimization)
24. [Deployment Runbooks](#24-deployment-runbooks)
25. [Compliance and Auditing](#25-compliance-and-auditing)

---

## 1. Deployment Philosophy

### 1.1 Principles

| Principle | Description |
|-----------|-------------|
| **Immutable artifacts** | Every deployment is a new image with a unique SHA. No hot-patching in production. No configuration drift between environments. |
| **Gradual rollout** | Every production change goes through canary → staged rollout → full deployment. No direct-to-all pushes. |
| **Observability-driven** | Deployments are gated on metrics (error rate, latency, cost). If metrics degrade, rollout stops automatically. |
| **Stateless services, stateful data** | Services can be killed and recreated at any time. Data stores require careful migration procedures. |
| **Rollback-first** | Every deployment plan includes a verified rollback procedure. Roll forward is preferred, but rollback must always be possible. |
| **GitOps for production** | ArgoCD reconciles desired state from Git. No manual `kubectl apply` in production. |

### 1.2 Deployment Modes vs Environments

| Deployment Mode | Environment(s) | Isolation | Infrastructure |
|----------------|---------------|-----------|----------------|
| SaaS (multi-tenant) | dev, staging, prod | RLS + per-tenant Qdrant collections | Shared EKS clusters per environment |
| Dedicated Cloud | enterprise-prod | Per-tenant RDS + Qdrant | Tenant-specific namespaces or clusters |
| Customer VPC | customer-prod | Full network isolation | Customer's AWS/GCP account |
| On-Prem K8s | customer-prod | Physical isolation | Customer's data center |
| Air-Gapped | customer-prod | No network egress | Customer's isolated network |

---

## 2. Local Development

### 2.1 Development Environment Options

| Option | Setup Time | Fidelity | Use Case |
|--------|-----------|----------|----------|
| Dev Container | 2 min (first: 5 min) | Medium | Full-stack development |
| Docker Compose | 1 min (first: 3 min) | High | Service integration testing |
| Local install | 5 min | Low | Quick backend changes |
| Tilt (K8s in dev) | Removed during cleanup | | |

### 2.2 Dev Container

```json
{
  "name": "SchemaIntern Development",
  "image": "mcr.microsoft.com/devcontainers/python:3.12",
  "features": {
    "ghcr.io/devcontainers/features/docker-in-docker:2": {},
    "ghcr.io/devcontainers/features/node:1": { "version": "22" }
  },
  "forwardPorts": [3000, 8100, 8200, 8300, 8400, 8500, 8600],
  "portsAttributes": {
    "3000": { "label": "Frontend" },
    "8100": { "label": "Public API" },
    "8200": { "label": "KE API" },
    "8300": { "label": "Model Router" },
    "8400": { "label": "Planner" },
    "8500": { "label": "Retriever" },
    "8600": { "label": "Context Layer" }
  },
  "postCreateCommand": ".devcontainer/setup.sh",
  "customizations": {
    "vscode": {
      "extensions": [
        "ms-python.python", "ms-python.mypy", "charliermarsh.ruff",
        "dbaeumer.vscode-eslint", "bradlc.vscode-tailwindcss",
        "redhat.vscode-yaml", "yzhang.markdown-all-in-one"
      ]
    }
  }
}
```

### 2.3 Docker Compose (Full Dev Stack)

```yaml
services:
  postgres:
    image: postgres:16
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]
    environment:
      POSTGRES_DB: opencode_dev
      POSTGRES_PASSWORD: dev_password
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
  ke-api:
    build:
      context: ../../
      dockerfile: infra/docker/Dockerfile.ke-api
    ports: ["8200:8200"]
    depends_on: [postgres]
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:dev_password@postgres:5432/opencode_dev
      LOG_LEVEL: DEBUG
  frontend:
    build:
      context: ../../frontend
      dockerfile: ../infra/docker/Dockerfile.frontend.dev
    ports: ["3000:3000"]
    volumes:
      - ../../frontend:/app
      - /app/node_modules
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8100

volumes:
  pgdata:
```

---

## 3. Docker Build Strategy

### 3.1 Multi-Stage Build Pattern

All services follow the same multi-stage build pattern:

```dockerfile
# Stage 1: Base — shared Python dependencies
FROM python:3.12-slim AS base
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock /app/
RUN uv sync --no-dev --frozen

# Stage 2: Dev — includes dev dependencies
FROM base AS dev
RUN uv sync --dev --frozen
COPY . /app/
CMD ["uv", "run", "fastapi", "dev", "src/backend/ke-api/main.py", "--port", "8200"]

# Stage 3: Test — runs tests in isolated environment
FROM dev AS test
RUN pytest tests/ -x --cov=src/backend/ke-api --cov-report=term

# Stage 4: Production — minimal runtime image
FROM python:3.12-slim AS prod
RUN groupadd -r opencode && useradd -r -g opencode -m -d /app opencode
COPY --from=base /app/.venv /app/.venv
COPY --from=base /app/src /app/src
COPY --from=base /app/pyproject.toml /app/
USER opencode
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8200/health')"
EXPOSE 8200
CMD ["uv", "run", "granian", "--interface", "asgi", "src.backend.ke-api.main:app", "--host", "0.0.0.0", "--port", "8200"]
```

### 3.2 Service Image Matrix

| Service | Base Image | Prod Size | Build Time | Cache Strategy |
|---------|-----------|-----------|------------|----------------|
| ke-api | python:3.12-slim | 180MB | 3 min | pip layer caching, uv cache mount |
| public-api | python:3.12-slim | 160MB | 3 min | Same |
| model-router | python:3.12-slim | 140MB | 2 min | Same |
| query-pipeline | python:3.12-slim | 350MB | 4 min | Same |
| query-pipeline-gpu | rocm/pytorch:rocm6.3.2 | 6GB | 15 min | ROCm base layer cached |
| schema-intel | python:3.12-slim | 250MB | 3 min | Same |
| learning-loop | python:3.12-slim | 200MB | 3 min | Same |
| frontend | node:22-alpine | 70MB | 4 min | npm cache, standalone output |

### 3.3 GPU Dockerfile

```dockerfile
FROM rocm/pytorch:rocm6.3.2_ubuntu22.04_py3.12_pytorch_release AS base
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock /app/
RUN uv sync --no-dev --frozen
COPY src/ /app/src/
RUN pip install vllm==0.6.0 --no-deps
USER opencode
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"
ENV HIP_VISIBLE_DEVICES=0
ENV GPU_MAX_HW_QUEUES=16
HEALTHCHECK --interval=30s --timeout=15s --start-period=120s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
EXPOSE 8000
CMD ["python", "-m", "src.backend.inference.server"]
```

### 3.4 Image Registry Strategy

| Registry | Environment | Retention | Access |
|----------|-------------|-----------|--------|
| ECR (AWS) | All | Untagged: 7d. Tagged: 180d | IAM-based |
| Docker Hub | Public images | N/A | Pull-through cache |
| Air-gapped bundle | On-prem | Per release | Internal registry |

Image tagging convention: `{registry}/{service}:{git-sha}` (immutable primary), `{registry}/{service}:main-{date}-{build}` (latest main), `{registry}/{service}:v{major}.{minor}.{patch}` (releases).

---

## 4. Dev Containers

| Configuration | Purpose | Services Included |
|--------------|---------|------------------|
| `backend` | Backend API development | postgres, ke-api |
| `frontend` | Frontend development | postgres, ke-api, public-api |
| `fullstack` | Full-stack development | All services (no GPU) |
| `pipeline` | Agent pipeline development | All services + mock inference |
| `infra` | Removed during cleanup | |

For GPU development, a GPU-enabled dev container is available at `.devcontainer/devcontainer-gpu.json` with `--gpus all` and `--shm-size 8g`.

---

## 5. CI/CD Pipeline Architecture

### 5.1 Pipeline Stages

```
Lint & Type → Unit Tests → Build Images → Push to ECR → Scan (Trivy)
    → Deploy to Dev → Smoke Tests → Integration Tests → E2E Tests → Perf Tests
    → Deploy to Staging → Smoke Tests → E2E Tests → Manual Approval
    → Canary (5% → 25%) → Deploy to Prod → Smoke Tests → Observe (24h)
```

### 5.2 CI Pipeline Rules

| Check | Tool | Threshold |
|-------|------|-----------|
| Python linting | ruff | No errors |
| Type checking | mypy | strict mode, no errors |
| Security scan | Trivy | No CRITICAL or HIGH |
| Code coverage | pytest-cov | >= 80% per service |
| Frontend lint | ESLint | No errors |
| Frontend types | TypeScript | strict mode, no errors |
| Secrets scan | detect-secrets | No committed secrets |

### 5.3 GitHub Environments and Gates

| Environment | Auto-Deploy | Approval Required |
|-------------|-------------|-------------------|
| Dev | On main push | None |
| Staging | After dev passes | PR review |
| Production | Manual | 2 tech leads + QA sign-off |

---

## 6. Environment Strategy

### 8.1 Environment Specifications

| Property | Dev | Staging | Production |
|----------|-----|---------|------------|
| Cluster | EKS (2 nodes) | EKS (4 nodes) | EKS (10+ nodes) |
| Node types | t3.medium | t3.large + 1 GPU | m5.xlarge + 4+ GPU |
| PostgreSQL | db.t3.small (single) | db.r6g.large (single) | db.r6g.xlarge (multi-AZ) |
| Qdrant | 1 replica | 3 replicas | 5+ replicas |
| Backups | None | Daily + WAL | Daily + WAL + cross-region |
| Cost/month | ~$500 | ~$3,000 | ~$15,000+ |

### 8.2 Data Strategy Per Environment

| Environment | Data Source | Freshness | PII |
|-------------|-------------|-----------|-----|
| Dev | Synthetic + anonymized prod | Weekly | No |
| Staging | Anonymized prod snapshot | Weekly | No |
| Production | Real customer data | Real-time | Yes |

---

## 7. Environment Promotion

### 9.1 Promotion Policy

| Step | From → To | Trigger | Approval | Rollback Window |
|------|-----------|---------|----------|-----------------|
| 1 | PR → Dev | Merge to main | CI checks pass | N/A |
| 2 | Dev → Staging | Dev tests pass | PR review | 2 hours |
| 3 | Staging → Prod canary | Manual approval | 2 tech leads | 30 min |
| 4 | Canary 5% → 25% | Healthy for 15 min | Auto | 15 min |
| 5 | 25% → 100% | Healthy for 30 min | Auto | Immediate |

### 9.2 Promotion Checklist

```
Pre-Deployment:
  [ ] All CI checks pass (12 checks)
  [ ] Trivy scan: no CRITICAL or HIGH vulnerabilities
  [ ] Integration tests pass on staging
  [ ] E2E tests pass on staging
  [ ] Performance tests: no regression > 10%
  [ ] DB migrations tested on staging
  [ ] Rollback procedure verified

Approval:
  [ ] Tech lead 1 approves
  [ ] Tech lead 2 approves
  [ ] QA sign-off

Post-Deployment:
  [ ] Canary (5%) healthy for 15 min
  [ ] Error rate < 0.1% above baseline
  [ ] P50 latency < 1.2x baseline
  [ ] Rollout to 25% → 100%
  [ ] Post-deployment monitoring (2 hr)
```

---

## 8. Blue/Green Deployment

### 10.1 Strategy

Maintain two parallel stacks (Blue = current, Green = new). Traffic switches atomically when Green is verified.

### 10.2 When to Use

- **Major version changes**: Breaking API changes, DB schema migrations
- **LLM model swaps**: New inference model needs validation before full switch
- **Infrastructure changes**: Node pool upgrades, cluster migrations
- **Compliance deployments**: Audit requires pre-deployment validation with production traffic

### 10.3 Blue/Green Script

```bash
# 1. Deploy Green (inactive) with new image
docker compose -f docker-compose.yml up -d green

# 2. Run smoke tests against Green
python infra/scripts/smoke-test.py --url ${GREEN_URL}

# 3. Switch traffic to Green (atomic)
docker compose -f docker-compose.yml up -d

# 4. Monitor for regression (5 min)
sleep 300
python infra/scripts/check-metrics.py --env prod

# 5. Retain Blue stack for rollback (cleanup after 48h)
```

---

## 9. Canary Deployment

### 11.1 Strategy

Route a small percentage of traffic to the new version, gradually increasing as confidence grows.

### 11.2 Phases

```
Phase 1: 5% traffic to new version (15 min observation)
Phase 2: 25% traffic to new version (30 min observation)
Phase 3: 100% traffic to new version
```

### 11.3 Canary Health Checks

| Metric | Threshold |
|--------|-----------|
| Error rate | < 0.1% |
| P50 latency | < 1.2x baseline |
| P95 latency | < 1.5x baseline |
| Success rate | > 99.5% |
| GPU utilization | < 95% |

### 11.4 Implementation

Canary uses Linkerd TrafficSplit for weight-based routing. The canary deployment runs alongside stable with a `-canary` service suffix. TrafficSplit weights are updated as confidence grows. If health checks fail at any phase, automated rollback removes the traffic split and destroys the canary deployment.

---

## 10. Rolling Updates

### 12.1 Default Strategy

Rolling updates are the default for stateless services:

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 1
    maxSurge: 1
```

### 12.2 Service-Specific Overrides

| Service | maxUnavailable | maxSurge | Rationale |
|---------|---------------|----------|-----------|
| ke-api | 1 | 1 | Conservative — maintain capacity |
| public-api | 1 | 2 | Surge handles traffic spikes |
| query-pipeline-gpu | 0 | 1 | Never go below target (expensive GPU) |

### 12.3 Progress Deadline

All rollouts have `progressDeadlineSeconds: 600` (10 min max). If pods don't become ready within this time, the rollout fails and alerts fire.

---

## 11. Rollback Strategy

### 13.1 Rollback Methods

| Method | Speed | Risk | When to Use |
|--------|-------|------|-------------|
| Docker Compose restart | 1-2 min | Low | Failed deployment (most common) |
| Git revert | 5-10 min | Medium | Configuration errors |
| Database restore | 30-60 min | High | Data corruption, bad migration |

### 13.2 Rollback Decision Matrix

| Symptom | Action | Timeout |
|---------|--------|---------|
| Error rate > 1% increase | Immediate rollback | 2 min |
| P95 latency > 2x baseline | Rollback after 5 min | 5 min |
| DB migration failed | Rollback migration + deployment | 10 min |
| GPU OOM or crash loop | Immediate rollback | 1 min |
| Security vulnerability | Emergency rollback | Immediate |

### 13.3 Database Rollback

Database rollbacks follow expand-contract pattern: prefer writing a new migration to reverting. If rollback is required, restore from pre-migration backup, verify integrity, re-apply legitimate changes, then re-deploy.

---

## 12. Secrets Management Operations

### 14.1 Architecture

```
[External Secrets Operator] ← [AWS Secrets Manager / HashiCorp Vault]
    → [Kubernetes Secrets] → [Pod Environment Variables]
```

### 14.2 Secret Categories

| Category | Examples | Rotation |
|----------|----------|----------|
| Database | PG passwords, Qdrant API key | 90 days |
| Inference | OpenAI API key, Anthropic key | 180 days |
| JWT | Signing key | 180 days |
| Service | Internal service tokens | 30 days |
| TLS | Certificates | 365 days |

### 14.3 Air-Gapped Secrets

For air-gapped deployments, secrets are pre-generated, encrypted with age/sops, and stored in the deployment bundle. Decryption happens during install.

---

## 13. Configuration Management

### 15.1 Configuration Layers

```
Code defaults → Helm values.yaml → Environment values → ConfigMap → Env vars → Feature flags
```

### 15.2 Feature Flag System

Runtime feature flags are managed through ConfigMap updates:

```json
{
  "bigquery_connector": false,
  "async_query": true,
  "graph_traversal": false,
  "learning_loop": true,
  "deepseek_v3_starter": false
}
```

Flag lifecycle: Dev (all togglable) → Staging (staging defaults) → Prod (deployment-bound).

---

## 14. Database Migration Operations

### 16.1 Principles

- **Roll forward, not back**: Prefer new migration over reverting old one
- **Expand-contract**: Add before removing (zero-downtime)
- **Backward-compatible**: N-1 code works with new schema
- **Migration-as-code**: All migrations in Git, tested in CI

### 16.2 Toolchain

| Tool | Purpose |
|------|---------|
| Alembic | Migration framework |
| SQLAlchemy 2.0 | ORM |
| Helm hook | Pre-upgrade job |

### 16.3 Expand-Contract Pattern

```
Phase 1 (Expand): ALTER TABLE ... ADD COLUMN nullable
Phase 2 (Migrate): Backfill data across deploys
Phase 3 (Contract): ALTER TABLE ... DROP COLUMN (N+1 release)
```

### 16.4 Migration Testing

```python
def test_all_migrations_up_and_down():
    """Every migration must have working upgrade AND downgrade."""
    config = Config()
    config.set_main_option("script_location", MIGRATION_DIR)
    # Upgrade to latest, verify tables, downgrade to base, verify no tables

def test_migration_idempotent():
    """Running migration twice should be safe."""
    # Should not error on second run
```

### 16.5 Dangerous Migration Patterns

| Pattern | Risk | Safe Alternative |
|---------|------|-----------------|
| DROP COLUMN | Existing queries fail | Add nullable first, deploy, then drop |
| ALTER COLUMN TYPE | Truncation errors | Add new column, migrate data, drop old |
| RENAME TABLE | All queries fail | Create view with old name |
| NOT NULL on existing | Violates existing rows | Backfill first, then add constraint |

---

## 15. Multi-Region Deployment

### 17.1 Architecture

Enterprise-tier feature (Year 2 target). Active-passive with warm standby.

| Region | Role | EKS | PostgreSQL | Qdrant | GPU |
|--------|------|-----|-----------|--------|-----|
| us-east-1 | Active | 10+ nodes | Primary (multi-AZ) | Primary | Active |
| us-west-2 | Warm | 3+ nodes | Cross-region replica | Read-only | Warm |
| eu-west-1 | Cold | 1 node | — | — | — |

### 17.2 Cross-Region Replication

| Data Store | Method | RPO | RTO |
|-----------|--------|-----|-----|
| PostgreSQL | Cross-region read replica | < 5 min | < 15 min |
| Qdrant | Snapshot + S3 cross-region | < 1h | < 2h |

### 17.3 Deployment Order

1. Deploy to secondary region first (warm it up)
2. Verify secondary health
3. Deploy to primary region
4. Update Route53 latency routing

---

## 16. Disaster Recovery Procedures

### 18.1 DR Tiers

| Tier | Applicable To | RPO | RTO |
|------|---------------|-----|-----|
| Bronze | Free / Starter | 24h | 4h |
| Silver | Pro | 4h | 1h |
| Gold | Enterprise | 5min | 15min |

### 18.2 DR Scenarios

**Single AZ Failure**: Auto-detected by cluster autoscaler. HPA scales up in remaining AZs. Multi-AZ RDS fails over (< 60s). Qdrant re-balances.

**Single Region Failure**: Route53 health check fails → notify on-call → promote cross-region PG replica → promote Qdrant read replica → scale up warm standby EKS → update DNS. Expected RTO: 15 min (Gold).

**Data Corruption**: STOP ALL QUERIES → identify last clean backup → restore PG from snapshot → verify integrity → re-point application → re-apply legitimate changes.

**GPU Node Failure**: Router falls back to cloud inference (GPT-4o). K8s pod scheduling was removed during cleanup.

### 18.3 DR Testing Schedule

| Test | Frequency | Scope |
|------|-----------|-------|
| Backup integrity | Daily | Automated restore test on staging |
| Single AZ failover | Weekly | Simulate AZ outage in dev |
| Full DR drill (staging) | Monthly | Complete failover |
| Full DR drill (prod) | Quarterly | Non-disruptive |
| Chaos engineering | Bi-annually | Network, DB, GPU failures |

---

## 17. High Availability Operations

### 19.1 Availability Targets

| Component | Target | Mechanism |
|-----------|--------|-----------|
| Public API | 99.95% | 3+ replicas, multi-AZ |
| KE API | 99.99% | 3+ replicas, PDB |
| Query pipeline | 99.9% | Cloud fallback on GPU failure |
| PostgreSQL | 99.995% | Multi-AZ RDS |
| Qdrant | 99.9% | 3-node cluster (N=3, R=2, W=2) |
| **Overall platform** | **99.9%** | Composite |

### 19.2 Graceful Shutdown

All pods implement a preStop hook: drain in-flight requests (5s sleep), signal health check failure, wait for LB drain (remaining grace period). Grace periods range from 15s (model-router) to 120s (query-pipeline-gpu).

### 19.3 Cost of HA

Multi-AZ deployment costs approximately 2x single-AZ (GPU nodes: $4K → $8K/mo, PostgreSQL: $200 → $400/mo).

---

## 18. GPU Deployment and Scheduling

### 20.1 Node Pool Architecture

```
[System Pool] t3.medium 2-5 nodes → system pods
[App Pool] m5.xlarge 3-10 nodes → app pods
[GPU Pool] p5.48xlarge 2-10 nodes → inference pods (AMD MI300X)
[Data Pool] r6g.xlarge 2-5 nodes → PostgreSQL, Qdrant, Redis
```

### 20.2 GPU Node Configuration

- AMD GPU device plugin DaemonSet on GPU nodes
- Node labels: `accelerator=amd-gpu`, `pool=gpu`
- Node taints: `dedicated=gpu:NoSchedule`
- Pod anti-affinity: max 1 GPU pod per node (required)
- Resources: `amd.com/gpu: 1` per pod

### 20.3 GPU HPA

Custom metric-based: scales on `inference_queue_depth` (target avg 5) and memory utilization (target 80%). Scale-up is aggressive (2 pods per 30s), scale-down is conservative (1 pod per 120s, 5 min stabilization window).

### 20.4 GPU Node Autoscaling

Karpenter provisioner for GPU nodes with consolidation (replace when empty, 5 min delay). Limits: 10 GPU nodes max.

---

## 19. AMD ROCm Deployment Procedures

### 21.1 GPU Node Bootstrap

1. Install ROCm drivers (`amdgpu-dkms`, `rocm`)
2. Deploy AMD GPU device plugin DaemonSet
3. Validate with `rocm-smi` and PyTorch tensor test

### 21.2 Inference Model Deployment

Models are deployed via Helm chart with model-specific values (GPU memory, pods per GPU). After deployment, model is registered with the Model Router via API.

### 21.3 Known ROCm Limitations

| Issue | Impact | Workaround |
|-------|--------|------------|
| Flash Attention 2 unavailable | ~15% slower inference | sdp backend |
| vLLM prefill ~10% slower | Higher P99 first-token latency | Over-provision 15% |
| No CUDA Graphs | Higher per-request overhead | Continuous batching |
| MPS not available on MI300X | No GPU sharing | Dedicated GPU per pod |

---

## 20. NVIDIA Deployment

### 22.1 Multi-Phase Plan

| Phase | Timeline | GPU Configuration |
|-------|----------|-------------------|
| 1 (MVP) | Now | AMD ROCm only |
| 2 | Y2 Q1 | Dual GPU pools (AMD + NVIDIA) |
| 3 | Y2 Q3 | Auto-detect GPU platform |
| 4 | Y3 | Mixed GPU, router selects best |

### 22.2 NVIDIA Setup

- NVIDIA device plugin DaemonSet (separate from AMD)
- Node labels: `accelerator=nvidia-gpu`, `gpu-platform=cuda`
- Same application image, different node selector
- Platform detected at runtime via `detect_gpu_platform()` (checks for `nvcc` or `rocm-smi`)

---

## 21. Enterprise On-Prem Deployment

### 23.1 Deployment Modes

| Mode | Network | Bundle Size | Upgrade Method |
|------|---------|-------------|----------------|
| Connected on-prem | Internal network | < 1GB | Docker Compose upgrade |
| Air-gapped | No network egress | 15-30GB | Pull + scripted upgrade |
| Customer VPC | Customer cloud | < 1MB (config) | CI/CD per customer |

### 23.2 Air-Gapped Bundle

```
schemaintern-airgapped-v1.0.0/
├── checksums.sha256
├── manifest.yaml
├── images/                    # All container images (docker save)
├── charts/                    # Helm charts with vendored deps
├── scripts/
│   ├── preflight-check.sh     # Verify GPU, storage
│   ├── load-images.sh         # Load all images
│   ├── install.sh             # Full installation
│   ├── upgrade.sh             # Version upgrade
│   ├── health-check.sh        # Post-install verification
│   └── uninstall.sh           # Clean removal
├── config/
│   ├── values-air-gapped.yaml
│   └── secrets.env.encrypted  # age/sops encrypted
├── docs/
└── support/
    ├── diagnostics.sh
    └── syslog-collector.sh
```

### 23.3 Pre-Flight Checks

| Check | Requirement |
|-------|-------------|
| Kubernetes | >= 1.28 |
| GPU | >= 1 AMD MI100+ or NVIDIA equivalent |
| Storage | >= 200GB available |
| Memory | >= 64GB (128GB recommended) |

### 23.4 On-Perm Upgrade Procedure

Pull-based: customer retrieves release bundle, runs `./scripts/upgrade.sh v1.1.0`. Script loads new images, runs DB migration, verifies health.

---

## 22. Monitoring Integration

### 24.1 Stack

| Component | Purpose | Retention |
|-----------|---------|-----------|
| Prometheus | Metrics | 30d local, 180d Thanos |
| Grafana | Dashboards | N/A |
| Loki | Logs | 30d |
| Tempo | Traces | 7d |
| OTel Collector | Collection | N/A |
| Alertmanager + PagerDuty | Alerts | N/A |

### 24.2 Deployment Alerts

| Alert | Condition | Severity |
|-------|-----------|----------|
| Pod CrashLoopBackOff | > 3 restarts in 5 min | Critical |
| Rollout stuck | Not ready after 10 min | Critical |
| GPU pod pending | > 5 min | Warning |
| DB migration failed | Job failed | Critical |
| Node NotReady | > 5 min | Critical |

---

## 23. Cost Optimization

### 25.1 Deployment-Level Levers

| Lever | Savings | Implementation |
|-------|---------|----------------|
| Spot instances (dev/staging) | 60-70% | Karpenter spotToPOD |
| Reserved GPU instances | 40% | 1yr commitment |
| HPA right-sizing | 20% | Continuous tuning |
| Dev shutdown nights/weekends | 70% dev cost | kube-downscaler |

### 25.2 Environment Budgets

| Environment | Monthly Budget | Optimization |
|-------------|---------------|--------------|
| Dev | $500 | 70% spot, auto-shutdown |
| Staging | $3,000 | 50% spot, data pruning |
| Prod (SaaS) | $15,000 | Reserved instances, GPU optimization |
| DR (warm) | $3,000 | Minimal compute, downsized storage |

---

## 24. Deployment Runbooks

### 26.1 Standard Deployment Runbook

```markdown
## Standard Deployment (Routine)

**Pre-flight**: [ ] Verify CI passes on main. [ ] Check staging health.
[ ] Review release notes.

**Deploy**: Run `./infra/scripts/deploy.sh prod <git-sha>`.

**Monitor**: Watch Grafana deployment dashboard for 15 min.
Check error rate, latency, GPU utilization.

**Verify**: Run smoke test suite.
Check canary health metrics.

**Complete**: Tag release in Git. Update release notes. Notify team.

## Emergency Rollback

**Trigger**: Error rate > 1%. P95 latency > 2x baseline.

**Action**: Run `./infra/scripts/rollback.sh prod`.

**Verify**: Check health endpoint. Verify error rate returns to baseline.

**Post-mortem**: Create incident report within 24h.
```

---

## 25. Compliance and Auditing

### 27.1 Deployment Audit Trail

Every deployment logs to the audit system:

```json
{
  "timestamp": "2026-07-10T16:30:00Z",
  "actor": "github-actions-bot",
  "action": "deploy",
  "environment": "production",
  "artifact": "ke-api:abc123def",
  "strategy": "canary",
  "result": "success",
  "duration_seconds": 845,
  "approvals": ["tech-lead-1", "tech-lead-2"]
}
```

### 27.2 Compliance Requirements

| Requirement | Implementation |
|-------------|----------------|
| SOC 2 | Immutable deployment audit trail. Change management process. |
| GDPR | Data classification in config. PII-free staging data. |
| HIPAA | BAA with cloud providers. Customer VPC deployment option. |

### 27.3 Deployment Approval Matrices

| Change Type | Dev | Staging | Production |
|-------------|-----|---------|------------|
| Bug fix | CI pass | PR review | 2 approvals + canary |
| Feature | CI pass | PR review | 2 approvals + canary |
| Config change | CI pass | PR review | 2 approvals + canary |
| Emergency fix | CI pass | CI pass | 1 approval + expedited canary |

---

## References

| Source | Relevance |
|--------|-----------|
| [Infrastructure-Specification.md](Infrastructure-Specification.md) | Infrastructure architecture, Docker |
| [Engineering-Standards.md](Engineering-Standards.md) §7-8 | CI/CD standards, git workflow, release strategy |
| [Security-Specification.md](Security-Specification.md) §9 | Secrets management, deployment security checklist |
| [Database-Specification.md](Database-Specification.md) §11 | Backup/recovery, migration procedures |
| [Performance-Specification.md](Performance-Specification.md) §10 | Scaling strategy, load testing |
| [ADR-009 Self-Hosted Inference](../decisions/ADR-009-Self-Hosted-Inference-Primary.md) | GPU inference deployment |
| [ModelRouter-Specification.md](ModelRouter-Specification.md) | Model routing, provider abstraction |
| [System-Architecture.md](../System-Architecture.md) §7 | Deployment architecture overview |
| [Deployment-Architecture.md](../Deployment-Architecture.md) | Deployment modes and configurations |
