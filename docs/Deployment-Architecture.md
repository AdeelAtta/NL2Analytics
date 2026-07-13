# Deployment Architecture

**Enterprise Data Intelligence Platform — Phase 2 Architecture & Design**

| Metadata | Value |
|----------|-------|
| **Author** | Founding CTO |
| **Date** | July 2026 |
| **Status** | Draft |
| **Version** | 1.0 |
| **Cross-References** | [System-Architecture.md](./System-Architecture.md), [Knowledge-Engine.md](./Knowledge-Engine.md), [Component-Design.md](./Component-Design.md), [API-Design.md](./API-Design.md), [Data-Flow.md](./Data-Flow.md) |

---

## 1. Deployment Principles

| Principle | Implication |
|-----------|-------------|
| **Deployment mode** | Docker Compose. K8s, Terraform, and Helm were removed. |
| **Self-hosted everything** | No external API dependencies for core functionality. All knowledge stores are self-hosted. |
| **Stateless services** | All components are stateless. State lives in Knowledge Engine stores. |

---

## 2. Kubernetes Cluster Architecture — Removed

Deployment uses Docker Compose instead of Kubernetes. See `infra/docker/docker-compose.yml`.

---

## 3. Component Service Map — Removed

Kubernetes service definitions were removed. Services run as Docker Compose containers.

---

## 4. Storage Architecture

### 4.1 PostgreSQL

| Component | Configuration | Storage |
|-----------|--------------|---------|
| **Engine** | PostgreSQL 16 with `pgvector` extension | — |
| **HA Mode** | Patroni (streaming replication, 1 primary + 2 replicas) | — |
| **Primary** | 8 vCPU, 32GB RAM, 500GB SSD (GP3) | Read-write |
| **Replica 1** | 8 vCPU, 32GB RAM, 500GB SSD | Read-only queries |
| **Replica 2** | 4 vCPU, 16GB RAM, 500GB SSD | Analytics/reporting queries |
| **Connection pooling** | PgBouncer (per-tenant connection limits) | — |
| **Backups** | pgBackRest, daily full + WAL archiving (30-day retention) | S3-compatible storage |
| **Failover** | Automatic via Patroni (RPO: <1MB, RTO: <30s) | — |

### 4.2 Qdrant — Removed

### 4.3 Redis — Removed

---

## 5. Multi-Tenancy Model

### 5.1 Isolation Strategy

| Layer | Strategy | Rationale |
|-------|----------|-----------|
| **Data** | Row-level tenant IDs in shared PostgreSQL tables. | Most cost-effective. Still fully isolated at query level. |
| **Performance** | Per-tenant cost ceilings + query priority queues. | No noisy-neighbor problems at moderate scale. |
| **Security** | Tenant ID in every API call (JWT claim). Verified by API Layer before forwarding. | Impossible for Tenant A to access Tenant B's data even with wrong config. |
| **Inference** | Shared GPU pool with fair scheduling. Premium tenants get dedicated GPU pods. | Cost efficiency for majority; performance guarantee for premium. |
| **Configuration** | Per-tenant configuration records in Configuration Store. | Fully customizable per tenant. |

### 5.2 Tenant Data Flow

```
User Request
    │
    ▼
API Layer extracts tenant_id from JWT
    │
    ▼
All downstream requests include tenant_id header
    │
    ▼
Knowledge Engine filters all queries by tenant_id
    │
    ▼
PostgreSQL: WHERE tenant_id = 'uuid'
```

### 5.3 Tenant Tiers and Resource Allocation

| Tier | Max Databases | Max Tables | Query Quota | GPU Priority | Storage Quota | Max Connections |
|------|--------------|------------|-------------|--------------|---------------|-----------------|
| Free | 1 | 10 | 100/mo | None (lowest priority) | 500MB | 5 |
| Starter | 3 | 100 | 200/seat/mo | Best-effort | 2GB | 10 |
| Pro | 10 | 500 | 1,000/seat/mo | Normal | 10GB | 25 |
| Enterprise | Unlimited | Unlimited | Custom | Dedicated (optional) | Custom | Custom |

---

## 6. Deployment Modes — Removed

Multi-mode K8s deployment (Cloud SaaS, Dedicated, VPC, On-Prem, Air-Gapped) was removed. The project uses a single Docker Compose deployment.

---

---

## 7. Networking — Removed

Istio service mesh networking was removed. Services communicate via Docker Compose internal networking.

---

## 8. CI/CD Pipeline — Removed

Terraform and Helm deployment stages were removed. CI/CD runs tests and builds Docker images via Docker Compose.

---

## 9. Observability Stack

### 9.1 Components

| Component | Tool | Purpose |
|-----------|------|---------|
| Metrics | Prometheus + Grafana | System metrics, business metrics |
| Logging | Grafana Loki (or ELK) | Structured log aggregation |
| Tracing | OpenTelemetry + Jaeger/Tempo | Distributed trace correlation |
| Alerting | Grafana Alertmanager | PagerDuty, Slack, email |
| Dashboards | Grafana | Per-service, per-tenant, business |
| Uptime | Checkly / synthetic monitors | External monitoring |

### 9.2 Key Dashboards

| Dashboard | Audience | Content |
|-----------|----------|---------|
| **System Health** | On-call | CPU/mem/disk per node + service, error rates, latency |
| **Query Pipeline** | Engineering | Per-stage latency, throughput, error rate, model routing distribution |
| **Knowledge Engine** | ML Team | Embedding latency, store query latency, ingestion throughput |
| **Guardrail** | Security | Block rate per layer, false positive/negative trends, top blocked resources |
| **Business** | CEO/Sales | Active users, queries/day, ARR, churn precursors, conversion funnel |
| **Tenant Health** | Support | Per-tenant: query count, error rate, storage usage, cost |

### 9.3 Critical Alerts

| Alert | Condition | Response Time |
|-------|-----------|---------------|
| API P95 latency > 5s | 5-minute sliding window | < 15 min |
| Error rate > 2% | 5-minute window | < 15 min |
| Guardrail false negative | Any occurrence | < 5 min (security incident) |
| Disk space > 80% | PostgreSQL | < 1 hour |
| GPU pod down | Any GPU pod unavailable | < 15 min |
| Knowledge Engine API down | All replicas unavailable | < 5 min (page) |

---

## 10. Infrastructure Cost Model — Removed

K8s/Qdrant/Redis cost estimates were removed. Current deployment uses Docker Compose with PostgreSQL.

---

## 11. Disaster Recovery

| Scenario | RPO | RTO | Recovery Strategy |
|----------|-----|-----|-------------------|
| Container crash | 0 | <30s | Docker restart |
| Data corruption | <24h | <4h | Point-in-time recovery from backup |
| Full data loss | <24h | <24h | Reprovision + backup restore |

---

## 12. References

| Source | Relevance |
|--------|-----------|
| [System-Architecture.md](./System-Architecture.md) | Component architecture deployed on this infrastructure |
| [Knowledge-Engine.md](./Knowledge-Engine.md) | Storage requirements for PostgreSQL (Qdrant removed) |
| [Component-Design.md](./Component-Design.md) | Resource requirements per component |
| [Technology-Recommendations.md](../Technical-Landscape/Technology-Recommendations.md) | Technology justification for infrastructure choices |
