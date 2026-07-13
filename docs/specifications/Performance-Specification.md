# Performance Specification

**Version**: 1.0.0 | **Status**: Approved | **Last Updated**: 2026-07-10

**Cross-References**:
- [Infrastructure-Specification.md](Infrastructure-Specification.md) — K8s HPA, node pools, GPU scheduling
- [API-Specification.md](API-Specification.md) — Endpoint latency budgets, pagination, streaming
- [AI-Agent-Specification.md](AI-Agent-Specification.md) — Agent latency budgets, model routing, retry strategy
- [KnowledgeEngine-Specification.md](KnowledgeEngine-Specification.md) — KE API latency, embedding pipeline
- [Database-Specification.md](Database-Specification.md) — Query optimization, indexing strategy, partitioning
- [Frontend-Specification.md](Frontend-Specification.md) — Frontend performance budgets, bundle size
- [Deployment-Specification.md](Deployment-Specification.md) — Config matrix, resource requests/limits
- [Security-Specification.md](Security-Specification.md) — Policy enforcement latency, rate limiting

---

## Table of Contents

1. [Latency Budgets](#1-latency-budgets)
2. [GPU Utilization](#2-gpu-utilization)
3. [Cache Strategy](#3-cache-strategy)
4. [Cost per Request](#4-cost-per-request)
5. [Model Routing](#5-model-routing)
6. [Embedding Cost](#6-embedding-cost)
7. [Storage Cost](#7-storage-cost)
8. [Queue Latency](#8-queue-latency)
9. [API Latency](#9-api-latency)
10. [Scaling Strategy](#10-scaling-strategy)
11. [Load Testing](#11-load-testing)
12. [Stress Testing](#12-stress-testing)
13. [Performance KPIs](#13-performance-kpis)
14. [Optimization Roadmap](#14-optimization-roadmap)
15. [Cost Dashboards](#15-cost-dashboards)
16. [Margin Analysis](#16-margin-analysis)

---

## 1. Latency Budgets

### 1.1 Query Pipeline End-to-End Latency

| Segment | P50 (ms) | P95 (ms) | P99 (ms) | Budget Owner |
|---------|----------|----------|----------|-------------|
| API overhead (auth + rate limit) | 10 | 30 | 50 | API Gateway |
| Intent classification | 100 | 200 | 400 | Intent Agent |
| Context retrieval | 160 | 370 | 750 | Retriever |
| Query planning | 400 | 800 | 1,600 | Planner Agent |
| SQL generation (simple) | 800 | 1,200 | 2,000 | Generator (SQLCoder-7b) |
| SQL generation (medium) | 1,500 | 3,000 | 5,000 | Generator (Qwen2.5-72B) |
| SQL generation (complex) | 3,000 | 5,000 | 8,000 | Generator (DeepSeek-V3) |
| Validation + repair | 300 | 500 | 800 | Validator + Repair |
| Policy enforcement (10 layers) | 150 | 300 | 450 | Policy Enforcement |
| DB execution (target DB) | 200 | 2,000 | 10,000 | Target Database |
| Result formatting | 20 | 50 | 100 | Executor |
| **Simple query (SQLCoder)** | **~2,090** | **~4,350** | **~6,000** | — |
| **Medium query (Qwen2.5)** | **~2,790** | **~6,150** | **~10,300** | — |
| **Complex query (DeepSeek)** | **~4,290** | **~8,150** | **~13,300** | — |

### 1.2 Streaming Latency (First Token)

With streaming, the user sees the first token much faster than total latency:

| Model | First Token (P50) | First Token (P95) |
|-------|------------------|------------------|
| SQLCoder-7b | 200ms | 400ms |
| Qwen2.5-72B | 500ms | 1,200ms |
| DeepSeek-V3 | 1,000ms | 2,500ms |

### 1.3 Streaming Timeline

```
Time: 0s     1s     2s     3s     4s     5s     6s     7s     8s
      |      |      |      |      |      |      |      |      |
API  [auth][intent][retrieval][planning]
      |      |      |      |
SQL  [streaming: first token appears here]
      |      |      |      |      |      |      |
DB   [execution]
      |      |
Result rendering: starts arriving as streaming completes
```

### 1.4 KE API Latency Budgets

| Operation | P50 (ms) | P95 (ms) | P99 (ms) | Scaling Factor |
|-----------|----------|----------|----------|---------------|
| Schema: read single table | 5 | 15 | 30 | O(1) per table |
| Schema: read all tables for DB | 15 | 30 | 60 | O(tables) |
| Schema: upsert (100 tables) | 200 | 400 | 800 | O(tables) |
| Vector: search (top 20, 100K vectors) | 30 | 80 | 150 | O(log n) |
| Vector: search (top 20, 1M vectors) | 50 | 120 | 250 | O(log n) |
| Vector: upsert (10 points) | 20 | 40 | 80 | O(1) |
| Graph: create node | 5 | 10 | 20 | O(1) |
| Graph: traverse (depth 3, 50K nodes) | 30 | 80 | 150 | O(depth * branching) |
| Graph: traverse (depth 5, 50K nodes) | 100 | 300 | 600 | O(depth * branching) |
| History: read last 50 | 10 | 20 | 40 | O(1) |
| History: write | 10 | 20 | 40 | O(1) |
| Feedback: write | 10 | 20 | 40 | O(1) |
| Audit: write | 10 | 20 | 40 | O(1) |
| Metrics: write | 5 | 10 | 20 | O(1) |
| **KE API overhead (per call)** | **2** | **5** | **10** | O(1) |

### 1.5 Batch Operation Latency Budgets

| Operation | Target | Max Acceptable | Frequency |
|-----------|--------|---------------|-----------|
| Schema sync (full, 200 tables) | < 10s | < 30s | On trigger (daily) |
| Schema sync (incremental, 10 tables) | < 5s | < 15s | Every 24h |
| LLM annotator (batch 50 columns) | < 30s | < 60s | On schema sync |
| Relationship inference (200 tables) | < 5s | < 15s | On schema sync |
| Embedding generation (batch 100 items) | < 500ms | < 2s | On schema sync + queries |
| Learning loop batch cycle (1K items) | < 16s | < 30s | Every 5 min |
| Metrics rollup (hourly) | < 10s | < 30s | Every hour |
| Metrics rollup (daily) | < 30s | < 60s | Every day |
| Partition cleanup | < 5s | < 15s | Daily |
| Backup (PG dump, 10GB) | < 15min | < 30min | Daily |

### 1.6 Budget Enforcement

| Budget | Threshold | Action |
|--------|-----------|--------|
| Query total P95 > 10s | 3 consecutive measurements | Alert + investigate stage |
| Policy enforcement P95 > 500ms | Any measurement | Alert + optimize policy layers |
| KE API P95 > 50ms | 3 consecutive measurements | Alert + scale KE service |
| DB execution P95 > 5s | 5 consecutive measurements | Alert + analyze slow queries |
| Learning cycle > 60s | Any measurement | Alert + reduce batch size |
| Schema sync > 120s | Any measurement | Alert + optimize connector |
| First token P50 > 1s | 3 consecutive measurements | Alert + check GPU utilization |
| Streaming tokens/sec < 20 | Any measurement | Alert + check model throughput |

---

## 2. GPU Utilization

### 2.1 GPU Specifications

| GPU | Memory | Compute Units | Peak TFLOPS (FP16) | Use Case |
|-----|--------|--------------|-------------------|----------|
| AMD MI300X | 192GB HBM3 | 40 GCD (304 CUs) | 653.7 | Primary inference |
| AMD MI250 | 128GB HBM2e | 220 CUs | 362.1 | Fallback/embedding |
| NVIDIA A100 (80GB) | 80GB HBM2e | 6912 CUDA cores | 312 | Future NVIDIA path |
| NVIDIA H100 | 80GB HBM3 | 18432 CUDA cores | 989 | Future NVIDIA path |

### 2.2 Model GPU Requirements

| Model | GPU Memory | Recommended GPU | Throughput (tokens/s) | Batch Size |
|-------|-----------|----------------|---------------------|-----------|
| BGE-M3 (embedding) | 2GB | Any GPU | 5,000+ | 128 |
| SQLCoder-7b (INT4) | 6GB | Shared MI300X | 120 | 8 |
| Qwen2.5-7B (INT4) | 6GB | Shared MI300X | 110 | 8 |
| Qwen2.5-72B (INT4) | 48GB | Dedicated MI300X | 35 | 2 |
| DeepSeek-V3 (INT4) | 72GB | Dedicated MI300X | 20 | 1 |
| DeepSeek-V3 (FP8) | 144GB | 2x MI300X | 15 | 1 |

### 2.3 GPU Utilization Targets

| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| GPU compute utilization | 70-85% | < 50% or > 95% | < 30% or > 98% |
| GPU memory utilization | 80-90% | < 60% or > 95% | < 40% or > 98% |
| GPU power draw | 70-85% of TDP | < 40% or > 95% | < 20% or > 98% |
| KV cache utilization | 70-90% | < 40% | < 20% |
| Model load time | < 30s | > 60s | > 120s |
| Token generation rate | > 75% of theoretical | < 50% | < 25% |

### 2.4 GPU Pod Density

| MI300X Pod Configuration | SQLCoder-7b | Qwen2.5-72B | DeepSeek-V3 | BGE-M3 |
|-------------------------|-------------|-------------|-------------|--------|
| Pods per GPU | 8 | 3 | 2 | 16 |
| Memory per pod | 16GB | 48GB | 72GB | 2GB |
| Concurrent requests per pod | 8 | 4 | 2 | N/A |
| Max throughput (tokens/s/GPU) | 960 | 105 | 40 | 80K+ |

### 2.5 GPU Memory Allocation

```
MI300X (192GB HBM3)
+-- OS + ROCm drivers: ~2GB
+-- vLLM/SGLang runtime: ~4GB
+-- KV cache: ~20GB (dynamically allocated)
+-- Model weights:
|   +-- SQLCoder-7b INT4: ~6GB (1 of 8 pods)
|   +-- Qwen2.5-72B INT4: ~48GB (1 of 3 pods)
|   +-- DeepSeek-V3 INT4: ~72GB (1 of 2 pods)
+-- Overhead/buffer: ~10-20GB
```

### 2.6 GPU Energy Efficiency

| Metric | MI300X | A100 (80GB) | H100 |
|--------|-------|-------------|------|
| TDP | 750W | 400W | 700W |
| Tokens/Watt (SQLCoder-7b) | 1.28 | 0.78 | 1.41 |
| Tokens/Watt (Qwen2.5-72B) | 0.047 | 0.025 | 0.050 |
| Cost/Watt (US avg) | $0.08/kWh | $0.08/kWh | $0.08/kWh |
| Annual power cost (8 GPUs) | $42,048 | $22,426 | $39,245 |

---

## 3. Cache Strategy

### 3.1 Cache Hierarchy

```
Layer 1: Browser (HTTP Cache)
  TTL: 5-60s depending on endpoint
  Scope: Per-browser
  Hit ratio target: 20%

Layer 2: CDN (CloudFront)
  TTL: 60s (dynamic), 24h (static)
  Scope: Global edge
  Hit ratio target: 40% (static), 10% (dynamic)

Layer 3: API Gateway (Cache uses PostgreSQL)
  Note: Redis was removed during cleanup

Layer 4: Application (In-memory)
  TTL: 5-60s
  Scope: Per-pod
  Hit ratio target: 30%

Layer 5: KE Store (PostgreSQL + Qdrant)
  TTL: Tenant-level TTL
  Scope: Global (within cluster)
  Hit ratio target: 90%
```

### 3.2 Cacheable vs Non-Cacheable

| Cacheable | TTL | Invalidation | Benefit |
|-----------|-----|-------------|---------|
| Schema metadata (databases, tables, columns) | 60s | On schema sync event | Avoids redundant DB reads |
| Table descriptions (LLM-generated) | 24h | On schema change | Avoids LLM re-generation |
| Embeddings (static, no user context) | 24h | On schema change | Avoids re-embedding |
| Query history (list, not detail) | 30s | On new query | Avoids DB query |
| Common query patterns | 1h | On pattern update | Faster retrieval |
| ABAC policy evaluation | 300s | On policy change | Avoids policy re-evaluation |
| Tenant settings | 60s | On settings update | Avoids DB query |
| Grafana dashboards | 30s | N/A | Faster dashboard loads |

| Non-Cacheable | Reason |
|---------------|--------|
| Query results | User-specific, time-sensitive |
| Streaming responses | Real-time by nature |
| Cost information | Must be real-time |
| Token counts | Unique per query |
| Query execution status | Must be real-time |
| Policy enforcement results | Must be fresh per query |

### 3.3 Cache Configuration

Cache uses PostgreSQL — Redis was removed during cleanup.

Caching is implemented via application-level in-memory caches backed by PostgreSQL for persistence:

### 3.4 Cache Invalidation Events

_Redis was removed during cleanup — cache invalidation uses PostgreSQL triggers._

### 3.5 Cache Hit Ratio Targets

| Cache Layer | Month 1 | Month 3 | Month 6 | Year 1 |
|-------------|---------|---------|---------|--------|
| Browser cache | 15% | 18% | 20% | 25% |
| CDN (CloudFront) | 30% | 35% | 40% | 50% |
| In-memory (per pod) | 20% | 25% | 30% | 35% |
| KE store (PG+Qdrant) | 70% | 80% | 85% | 90% |
| **Composite effective** | **~55%** | **~65%** | **~70%** | **~75%** |

### 3.6 Cache Miss Penalty Budget

| Cache Layer | Hit Cost | Miss Cost | Penalty Ratio |
|-------------|----------|-----------|---------------|
| PG cache (schema) | 2ms | 15ms | 7.5x |
| PG cache (embedding) | 2ms | 30ms | 15x |
| CDN (static assets) | 5ms | 200ms | 40x |
| KE store (vector search) | 30ms | 30ms (no miss penalty) | 1x |

---

## 4. Cost per Request

### 4.1 Per-Query Cost Model

| Model Tier | Cost per Query | % of Queries | Weighted Cost |
|------------|---------------|-------------|---------------|
| SQLCoder-7b-2 (simple) | $0.0003 | 50% | $0.00015 |
| Qwen2.5-72B (medium) | $0.002 | 35% | $0.00070 |
| DeepSeek-V3 (complex) | $0.01 | 10% | $0.00100 |
| GPT-4o (fallback) | $0.02 | 5% | $0.00100 |
| **Weighted average** | — | 100% | **$0.00285** |
| Safety buffer (2x for retries/repairs) | — | — | **~$0.0057** |

### 4.2 Cost Breakdown by Pipeline Stage

| Stage | Cost per Query | % of Total | Includes |
|-------|---------------|-----------|----------|
| Intent classification | $0.00010 | 2.9% | Small model or rule-based (CPU) |
| Query embedding | $0.00001 | 0.3% | BGE-M3 (negligible GPU cost) |
| Context retrieval | $0.00010 | 2.9% | Qdrant read + DB reads |
| SQL generation (primary) | $0.00285 | 83.8% | Weighted avg across tiers |
| Validation | $0.00005 | 1.5% | sqlglot parse (no LLM) |
| Repair (avg 0.3x queries) | $0.00030 | 8.8% | 30% of queries need repair |
| Policy Enforcement (deterministic) | $0.00001 | 0.3% | Rule-based (no LLM) |
| **Total per query** | **~$0.00341** | **100%** | — |

### 4.3 Cost by Query Complexity

| Query Type | % of Traffic | Cost/Query | Total Cost/1K Queries |
|-----------|-------------|-----------|---------------------|
| Simple (single table, no join) | 45% | $0.0015 | $0.68 |
| Medium (2-3 table join, aggregation) | 35% | $0.0035 | $1.23 |
| Complex (4+ tables, CTE, window) | 15% | $0.0150 | $2.25 |
| Very complex (multi-DB, graph traversal) | 5% | $0.0300 | $1.50 |
| **Weighted total** | **100%** | **$0.0034** | **$3.40** |

### 4.4 Revenue per Query by Tier

| Plan | Monthly Seat | Queries/Seat | Revenue/Query | Cost/Query | Gross Margin |
|------|-------------|-------------|---------------|------------|-------------|
| Free | $0 | 50 | $0.00 | $0.0034 | -infinite (loss leader) |
| Starter | $50 | 200 | $0.25 | $0.0034 | 98.6% |
| Pro | $150 | 1,000 | $0.15 | $0.0034 | 97.7% |
| Enterprise | Custom | Custom | ~$0.10 | $0.0034 | ~96.6% |

### 4.5 Cost per Request by Deployment Mode

| Mode | Cost/Query | Breakdown |
|------|-----------|-----------|
| SaaS (shared, 100 tenants) | $0.0034 | Inference: $0.00285, Infra: $0.0005, Storage: $0.00005 |
| Dedicated Cloud | $0.0045 | Inference: $0.00285, Infra: $0.0015, Storage: $0.00015 |
| Customer VPC | $0.000 (customer infra) | Inference: $0.00285 (our GPU) or customer GPU |
| On-Prem | $0.000 (customer infra) | Customer pays all infra |

### 4.6 Cost per Query Response

Every query response includes cost breakdown for transparency and debugging:

```json
{
  "cost": {
    "total": 0.0034,
    "breakdown": {
      "intent": 0.0001,
      "embedding": 0.00001,
      "retrieval": 0.0001,
      "generation": 0.00285,
      "validation": 0.00005,
      "repair": 0.0003,
      "policy_enforcement": 0.00001
    },
    "model_used": "qwen2.5-72b",
    "tokens_in": 2840,
    "tokens_out": 312,
    "cache_hit": false,
    "gpu_time_ms": 1200
  }
}
```

---


## 5. Model Routing

### 5.1 Router Architecture

```
User Query
    |
    v
[Intent Classifier] (CPU, < 50ms)
    |
    +-- Simple (known tables, single intent)
    |   +-- SQLCoder-7b-2 ($0.0003) -- 50% of queries
    |
    +-- Medium (multi-table, aggregations)
    |   +-- Qwen2.5-72B ($0.002) -- 35% of queries
    |
    +-- Complex (CTE, window functions, fuzzy intent)
    |   +-- DeepSeek-V3 ($0.01) -- 10% of queries
    |
    +-- Edge case (ambiguous, multi-DB, rapid retry)
        +-- GPT-4o ($0.02) -- 5% of queries
```

### 5.2 Router Decision Logic

```python
# lib/model_router.py
class ModelRouter:
    def __init__(self):
        self.rules = [
            RouteRule(
                name="simple",
                condition=lambda q: (
                    q.table_count <= 2
                    and q.join_count == 0
                    and q.aggregation == "none"
                    and q.complexity_score < 0.3
                ),
                model="sqlcoder-7b-2",
                cost=0.0003,
                latency_p50=800,
                confidence_min=0.70,
            ),
            RouteRule(
                name="medium",
                condition=lambda q: (
                    q.table_count <= 4
                    and q.join_count <= 2
                    and q.aggregation in ("group_by", "count", "sum")
                    and q.complexity_score < 0.6
                ),
                model="qwen2.5-72b",
                cost=0.002,
                latency_p50=1500,
                confidence_min=0.75,
            ),
            RouteRule(
                name="complex",
                condition=lambda q: (
                    q.table_count <= 8
                    and q.join_count <= 4
                    and q.complexity_score < 0.85
                ),
                model="deepseek-v3",
                cost=0.01,
                latency_p50=3000,
                confidence_min=0.80,
            ),
            RouteRule(
                name="fallback",
                condition=lambda _: True,  # Catch-all
                model="gpt-4o",
                cost=0.02,
                latency_p50=4000,
                confidence_min=0.85,
            ),
        ]

    async def route(self, query_intent: QueryIntent) -> RouteDecision:
        for rule in self.rules:
            if rule.condition(query_intent):
                return RouteDecision(
                    model=rule.model,
                    cost=rule.cost,
                    estimated_latency=rule.latency_p50,
                )

        return RouteDecision(model="gpt-4o", cost=0.02, estimated_latency=4000)
```

### 5.3 Router Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| Router decision latency | < 5ms | Instrumentation |
| Simple classification accuracy | > 95% | A/B comparison |
| Medium classification accuracy | > 90% | A/B comparison |
| Complex classification accuracy | > 85% | A/B comparison |
| Fallback rate | < 5% | Monthly tracking |
| Wrong routing (model too weak) | < 10% | Repair rate tracking |
| Wrong routing (model too expensive) | < 5% | Cost tracking |

### 5.4 Fallback Escalation

If a model fails or produces invalid SQL, the router escalates to the next tier:

```
SQLCoder-7b fail -> Qwen2.5-72B ($0.002 extra)
Qwen2.5-72B fail -> DeepSeek-V3 ($0.008 extra)
DeepSeek-V3 fail -> GPT-4o ($0.01 extra)
GPT-4o fail -> Return error to user
```

Escalation budget: Max 2 escalations per query (cost cap).

### 5.5 Model Pool Sizing

| Model | GPU Nodes | Pods per Node | Total Capacity | Max Concurrent |
|-------|-----------|--------------|----------------|---------------|
| SQLCoder-7b | 2 | 8 | 16 pods (192 req/s) | 128 |
| Qwen2.5-72B | 3 | 3 | 9 pods (36 req/s) | 36 |
| DeepSeek-V3 | 2 | 2 | 4 pods (8 req/s) | 8 |
| BGE-M3 | 1 | 16 | 16 pods (80K tok/s) | 256 |
| GPT-4o | N/A (API) | N/A | Unlimited | API rate limit |

---

## 6. Embedding Cost

### 6.1 Embedding Model: BGE-M3

| Parameter | Value |
|-----------|-------|
| Model | BAAI/bge-m3 |
| Embedding dimension | 1024 |
| Dense + Sparse | Both (hybrid search) |
| Max tokens | 8192 |
| Hardware | CPU or GPU (GPU preferred) |
| Batch size | 128 |
| Throughput (GPU) | 5,000+ items/second |
| Throughput (CPU) | 200 items/second |
| Memory | 2GB (GPU), 4GB (CPU) |

### 6.2 Embedding Costs by Operation

| Operation | Items/Batch | Batches | Total Items | GPU Time | Compute Cost |
|-----------|------------|---------|-------------|----------|-------------|
| Initial schema sync (200 tables) | 100 | 10 | 1,000 (tables + columns) | 0.2s | ~$0.00001 |
| Incremental sync (10 tables) | 10 | 1 | 50 | 0.01s | ~$0.000001 |
| Query embedding | 1 | 1 | 1 | 0.2ms | ~$0.0000001 |
| Learning loop re-embedding | 50 | 1 | 50 | 0.01s | ~$0.000001 |
| Bulk re-embed (all schemas, monthly) | 100 | 100 | 10,000 | 2s | ~$0.0001 |

BGE-M3 is self-hosted on a shared GPU. Compute costs are essentially free (amortized across all operations). The primary cost is GPU electricity (~$0.02/hr).

### 6.3 Embedding Storage Cost

| Component | Per Table | Per Database (200 tables) | Per Tenant |
|-----------|----------|--------------------------|------------|
| Dense vectors (1024d, float32) | 4KB | 800KB | ~20MB |
| Sparse vectors | 1KB | 200KB | ~5MB |
| Metadata | 0.5KB | 100KB | ~2.5MB |
| **Total per component** | **~5.5KB** | **~1.1MB** | **~27.5MB** |

Storage cost: ~$0.80/tenant/month for 20K vectors.

---

## 7. Storage Cost

### 7.1 Data Volume by Tenant

| Data Category | Monthly Growth | 6 Months | 12 Months | Unit Cost | Monthly Cost |
|--------------|---------------|----------|-----------|-----------|-------------|
| PostgreSQL (query history, 500 queries/mo * 2KB) | 1MB | 6MB | 12MB | $0.115/GB | $0.0001 |
| PostgreSQL (feedback, 500 items * 500B) | 0.25MB | 1.5MB | 3MB | $0.115/GB | $0.00003 |
| PostgreSQL (schema cache, 200 tables) | Static | Static | Static | $0.115/GB | ~$0.02 |
| Qdrant (vectors, 20K) | Static | Static | Static | $0.08/GB | ~$0.0016 |
| Qdrant (payloads) | 5MB | 30MB | 60MB | $0.08/GB | $0.005 |
| Logs (Loki, 100MB/mo) | 100MB | 600MB | 1.2GB | $0.05/GB | $0.005 |
| Traces (Tempo, 50MB/mo) | 50MB | 300MB | 600MB | $0.03/GB | $0.0015 |
| **Total per tenant** | **~156MB/mo** | **~940MB** | **~1.9GB** | **—** | **~$0.03/mo** |

### 7.2 Storage Cost by Environment

| Environment | Storage Type | Total Volume | Monthly Cost |
|-------------|-------------|-------------|-------------|
| Dev | gp3 EBS | 200GB | $20 |
| Staging | gp3 EBS | 500GB | $50 |
| Production (100 tenants) | io2 EBS + S3 | 2TB | $800 |
| Production (1K tenants) | io2 EBS + S3 | 8TB | $3,000 |
| Backups (S3) | S3 Standard | 3TB (100 tenants) | $90 |
| Cold storage | S3 Glacier | 10TB | $100 |

### 7.3 Storage Optimization Levers

| Lever | Savings | Complexity | Timeline |
|-------|---------|-----------|----------|
| Qdrant on_disk_payload | 40% RAM savings | Low | Week 1 |
| PostgreSQL table partitioning (monthly) | 30% query improvement | Low | Month 2 |
| Log compression (Loki) | 50% storage reduction | Low | Week 1 |
| Trace sampling reduction (1% -> 0.5%) | 50% trace storage | Low | Month 2 |
| S3 lifecycle: Standard -> IA -> Glacier | 60% backup cost | Low | Week 1 |
| Pg_dump compression (level 9) | 30% smaller backups | None | Week 1 |

---

## 8. Queue Latency

### 8.1 Queue Architecture

```
[Request] -> [Load Balancer] -> [In-Memory Queue (per pod)] -> [Worker Pool]
                                  +-- Max queue depth: 100
                                  +-- Max wait: 2s
                                  +-- Overflow: HTTP 503
                                  +-- Backpressure signal: Reduce HPA metric
```

### 8.2 Queue Latency Budgets

| Component | Queue Type | P50 Wait | P95 Wait | P99 Wait | Max Depth |
|-----------|-----------|----------|----------|----------|-----------|
| API request (CPU) | In-memory (per pod) | 10ms | 50ms | 100ms | 100 |
| API request (GPU inference) | vLLM continuous batch | 50ms | 200ms | 500ms | 256 |
| Learning loop feedback | PostgreSQL (batch poll) | 100ms | 500ms | 2s | 10,000 |
| Schema sync requests | In-memory (background) | 50ms | 100ms | 200ms | 10 |
| Embedding requests | In-memory (batch) | 20ms | 100ms | 200ms | 1,000 |
| WebSocket events | Channel buffer | 5ms | 20ms | 50ms | 100 |

### 8.3 vLLM Queue Configuration

```
# vLLM inference server configuration
--max-num-seqs 256         # Max sequences in queue
--max-num-batched-tokens 8192  # Max tokens per batch
--gpu-memory-utilization 0.90
--enforce-eager False
--max-model-len 16384

# Queue behavior
# - Batch requests together up to max_num_seqs
# - Dynamic batching: wait up to 30ms for more requests
# - If queue full, reject with 503
# - Client retries with exponential backoff
```

### 8.4 Load Shedding

| Load Level | Action | Trigger |
|-----------|--------|---------|
| Normal | All requests processed | Queue depth < 50 |
| Elevated | Reduce batch sizes, increase HPA | Queue depth > 50, sustained 30s |
| High | Start shedding non-critical requests | Queue depth > 80, sustained 30s |
| Critical | Shed all non-query requests | Queue depth > 95, sustained 10s |
| Overload | Return 503 to all new requests | Queue full (100) |

---

## 9. API Latency

### 9.1 Endpoint Latency Budgets

| Endpoint | P50 (ms) | P95 (ms) | P99 (ms) | Caching |
|----------|----------|----------|----------|---------|
| POST /v1/query (simple) | 2,500 | 5,000 | 7,000 | None (non-cacheable) |
| POST /v1/query (medium) | 3,500 | 7,000 | 11,000 | None |
| POST /v1/query (complex) | 5,000 | 9,000 | 14,000 | None |
| GET /v1/query/{id}/status | 10 | 30 | 50 | None |
| GET /v1/query/{id}/stream | 5 (TTFB) | 20 | 50 | None |
| GET /v1/schema/databases | 20 | 50 | 100 | Redis (60s) |
| GET /v1/schema/database/{id} | 30 | 80 | 150 | Redis (60s) |
| GET /v1/schema/table/{id} | 50 | 100 | 200 | Redis (120s) |
| POST /v1/schema/sync | 10,000 | 30,000 | 60,000 | None |
| GET /v1/history | 50 | 150 | 300 | Redis (30s) |
| GET /v1/history/{id} | 30 | 80 | 150 | Redis (60s) |
| GET /v1/settings | 20 | 50 | 100 | Redis (300s) |
| PUT /v1/settings | 50 | 100 | 200 | Invalidates cache |
| POST /v1/feedback | 30 | 60 | 100 | None |
| POST /v1/auth/login | 200 | 500 | 1,000 | None |
| POST /v1/auth/refresh | 50 | 100 | 200 | None |
| GET /v1/admin/usage | 500 | 2,000 | 5,000 | Redis (60s) |
| GET /v1/admin/teams | 100 | 300 | 500 | Redis (30s) |
| GET /health | 5 | 10 | 20 | None |

### 9.2 API Latency by Request Size

| Payload Size | P50 (ms) | P95 (ms) | Notes |
|-------------|----------|----------|-------|
| < 1KB | 10 | 30 | Most API requests |
| 1KB - 10KB | 20 | 60 | Schema data |
| 10KB - 100KB | 50 | 150 | Query results (small) |
| 100KB - 1MB | 100 | 300 | Query results (large) |
| > 1MB | 200 | 600 | Paginated or stream |

### 9.3 API Overhead Breakdown

| Component | P50 (ms) | % of Overhead |
|-----------|----------|--------------|
| TLS handshake (new connection) | 30 | 30% |
| Connection pool wait | 5 | 5% |
| Request parsing | 2 | 2% |
| Auth middleware | 5 | 5% |
| Rate limit check | 3 | 3% |
| Authorization (RBAC) | 5 | 5% |
| Authorization (ABAC) | 10 | 10% |
| Request validation | 2 | 2% |
| Response serialization | 8 | 8% |
| Response compression | 5 | 5% |
| **Total overhead** | **~75** | **75%** |
| Keep-alive (no TLS handshake) | ~45 | — |

---

## 10. Scaling Strategy

### 10.1 Horizontal Scaling

| Service | Scaling Metric | Min | Max | CPU Target | Memory Target |
|---------|---------------|-----|-----|-----------|--------------|
| public-api | CPU | 2 | 20 | 70% | 80% |
| ke-api | CPU | 2 | 10 | 70% | 80% |
| query-pipeline (CPU) | CPU | 2 | 20 | 60% | 80% |
| query-pipeline (GPU) | Inference queue depth | 2 | 10 | N/A | N/A |
| frontend | CPU | 2 | 10 | 70% | 80% |
| schema-intel | CPU | 1 | 5 | 70% | 80% |
| learning-loop | CPU | 1 | 2 | 70% | 80% |

### 10.2 Vertical Scaling Thresholds

When HPA reaches 80% of max replicas for > 30 minutes, trigger vertical scaling review:

| Metric | Current | Upgrade To | Cost Impact |
|--------|---------|-----------|-------------|
| public-api 20 pods at 70% CPU | t3.large | t3.xlarge | +$25/pod/mo |
| ke-api 10 pods at 70% CPU | t3.large | t3.xlarge | +$25/pod/mo |
| PostgreSQL at 80% CPU | db.r6g.large | db.r6g.xlarge | +$200/mo |
| Qdrant at 80% memory | m6i.xlarge | m6i.2xlarge | +$250/mo |

### 10.3 Database Scaling Stages

| Stage | Tenants | PostgreSQL | Qdrant | Strategy | Cost/Tenant |
|-------|---------|-----------|--------|----------|-------------|
| 1 | < 100 | db.r6g.large | 3-node cluster | Baseline shared | $202 |
| 2 | 100-500 | db.r6g.xlarge + read replicas | 5-node + replicas | Vertical + read replicas | $95 |
| 3 | 500-1K | db.r6g.2xlarge + pgpool | 7-node + sharding | Vertical + read replicas | $65 |
| 4 | 1K-5K | db.r6g.4xlarge, per-tenant DBs | Per-tenant collections | Horizontal (DB per tenant) | $47 |
| 5 | 5K-10K | Aurora Global Database | Multi-region Qdrant | Global scale | $35 |

### 10.4 GPU Scaling Plan

| Stage | Queries/Day | GPU Nodes | Configuration | GPU Cost/Month |
|-------|------------|-----------|---------------|---------------|
| 1 | < 10K | 2 MI300X | All models shared | $10,000 |
| 2 | 10K-50K | 4 MI300X | Dedicated small + large pools | $20,000 |
| 3 | 50K-200K | 8 MI300X | Per-model node pools | $40,000 |
| 4 | 200K-1M | 16 MI300X | Multi-region GPU pools | $80,000 |
| 5 | 1M+ | 32+ MI300X | Global GPU fleet | $160,000+ |

### 10.5 Queue-Based GPU Scaling

GPU pods scale on custom metric (inference queue depth) via Prometheus Adapter:

```
# Prometheus adapter config
seriesQuery: >
  avg by (pod) (vllm:num_requests_waiting)
resources:
  overrides:
    namespace: { resource: "namespace" }
    pod: { resource: "pod" }
metricsQuery: >
  avg by (<<.GroupBy>>) (
    vllm:num_requests_waiting{namespace="schemaintern"}
  )

# HPA using custom metric
metrics:
- type: Pods
  pods:
    metric:
      name: vllm_requests_waiting
    target:
      type: AverageValue
      averageValue: 5
```

### 10.6 Cluster Autoscaler Configuration

```
# Cluster autoscaler per node pool
system:     min 2, max 5,  scale-down after 10m idle
ke-store:   min 2, max 5,  scale-down disabled (stateful)
cpu-pool:   min 2, max 15, scale-down after 5m idle
gpu-pool:   min 2, max 10, scale-down after 15m idle (slow start)
```

---


## 11. Load Testing

### 11.1 Load Testing Scenarios

| Scenario | Target | Duration | Ramp | Sessions | Think Time |
|----------|--------|----------|------|----------|-----------|
| Baseline | Establish P50/P95/P99 | 10 min | 0 | 5 | None |
| Light load | 10 QPS | 30 min | 5 min | 10 | 3s |
| Medium load | 50 QPS | 60 min | 10 min | 50 | 2s |
| Heavy load | 100 QPS | 60 min | 15 min | 100 | 1s |
| Peak | 200 QPS | 30 min | 20 min | 200 | None |
| Stress | 500 QPS (max) | 15 min | 10 min | 500 | None |
| Soak | 50 QPS sustained | 4 hours | 10 min | 50 | 2s |
| Burst | 0 -> 200 QPS instantly | 5 min | Instant | 200 | None |

### 11.2 Load Test Profiles

```python
# load_tests/test_profiles.py
LOAD_PROFILES = {
    "baseline": {
        "query_mix": {
            "simple_select": 0.60,
            "aggregation": 0.15,
            "join": 0.10,
            "complex": 0.10,
            "edge_case": 0.05,
        },
        "db_mix": {
            "postgresql": 0.50,
            "mysql": 0.30,
            "bigquery": 0.20,
        },
        "user_mix": {
            "api_key": 0.70,
            "oauth": 0.20,
            "saml": 0.10,
        },
        "result_size": {
            "small (<100 rows)": 0.60,
            "medium (100-1K rows)": 0.25,
            "large (1K-10K rows)": 0.10,
            "xlarge (>10K rows)": 0.05,
        },
    },
}
```

### 11.3 Success Criteria

| Metric | Baseline | Light | Medium | Heavy | Peak | Soak |
|--------|----------|-------|--------|-------|------|------|
| P50 latency | < 3s | < 3.5s | < 4s | < 5s | < 6s | < 4s |
| P95 latency | < 6s | < 7s | < 8s | < 10s | < 12s | < 8s |
| P99 latency | < 8s | < 10s | < 12s | < 15s | < 18s | < 12s |
| Error rate | < 0.1% | < 0.1% | < 0.5% | < 1% | < 2% | < 0.5% |
| GPU utilization | < 50% | < 60% | < 70% | < 80% | < 90% | < 70% |
| CPU utilization | < 40% | < 50% | < 60% | < 70% | < 85% | < 60% |
| Memory utilization | < 50% | < 55% | < 60% | < 70% | < 80% | < 60% |
| Queue depth | < 5 | < 20 | < 50 | < 80 | < 100 | < 50 |
| 503 rate | 0% | 0% | 0% | < 1% | < 5% | 0% |

### 11.4 Load Test Tools

| Tool | Purpose | Configuration |
|------|---------|--------------|
| k6 | API load testing, metrics | scripts/load/k6/ |
| Locust | User simulation with think times | scripts/load/locust/ |
| ghz | gRPC load testing | scripts/load/ghz/ |
| custom | NL2SQL query replay | scripts/load/query-replay/ |

### 11.5 Query Replay Tests

```
# Load test with production query replay
1. Record anonymized queries from production (1 day)
2. Replay at various rates (1x, 2x, 5x, 10x)
3. Compare latency distributions
4. Identify regression in P99 within 10% of baseline
```

---

## 12. Stress Testing

### 12.1 Resource Exhaustion Tests

| Test | Method | Expected Behavior |
|------|--------|------------------|
| CPU exhaustion | Spin up CPU workers | HPA scales, latency increases < 50% |
| Memory pressure | Allocate large objects | OOMKiller kills offending pod, restart < 10s |
| GPU OOM | Send large batch requests | vLLM rejects, returns 503 |
| Disk full | Fill temporary volume | Read-only mode, alert fires |
| Network congestion | Simulate 50ms+ latency | Retry mechanism engages, no data loss |
| Connection pool exhaustion | Open 1000 concurrent conns | Pool blocks, queue builds, 503 after timeout |
| File descriptor limit | Open 10K connections | OS closes oldest idle connections |

### 12.2 Failure Injection Tests

| Failure | Method | Expected Recovery |
|---------|--------|------------------|
| PostgreSQL primary failover | Stop primary | Read replica promoted in < 30s, connections retry |
| Qdrant node failure | Kill 1/3 nodes | Remaining nodes serve reads, rebalance in < 2 min |
| Redis crash | Kill Redis pod | Cache disabled, services continue degraded |
| GPU node failure | Remove GPU node | Inference re-scheduled on remaining nodes, capacity reduced |
| API pod crash | Kill 50% of pods | HPA scales up replacements in < 60s |
| K8s node failure | Drain 1 node | Pods rescheduled in < 2 min |
| DNS failure | Block DNS | Services use cached DNS, retry TTL |
| TLS certificate expiry | Use expired cert | Connection fails with clear error message |

### 12.3 Chaos Engineering Schedule

```
Weekly (automated, canary):
  - Single pod kill (API, KE, frontend)
  - Single node drain (CPU pool)
  - Network latency injection (+20ms)

Monthly (automated, staging):
  - 50% pod kill
  - PostgreSQL primary failover
  - Redis cluster failure
  - DNS failure (30 min)
  - Simultaneous GPU + CPU node failure

Quarterly (manual, staging):
  - Full DR failover (region -> region)
  - Complete cluster rebuild from IaC
  - Simulated data center loss
  - Air-gapped deployment test
```

### 12.4 Success Criteria for Stress Tests

| Area | Pass | Fail |
|------|------|------|
| Error rate | < 5% during, 0% after | > 10% or data loss |
| Recovery time | < 5 min | > 15 min |
| Data integrity | No data loss | Any data loss |
| Undetected failures | 0 | Any |

---

## 13. Performance KPIs

### 13.1 Query Performance KPIs

| KPI | Target | Measurement | Reporting |
|-----|--------|-------------|-----------|
| P50 query latency (all) | < 3s | Distribution over 1h window | Dashboard, daily |
| P95 query latency (simple) | < 5s | Distribution over 1h window | Dashboard, daily |
| P95 query latency (medium) | < 7s | Distribution over 1h window | Dashboard, daily |
| P95 query latency (complex) | < 11s | Distribution over 1h window | Dashboard, daily |
| P99 query latency | < 8s (overall) | Distribution over 1h window | Dashboard, daily |
| SQL generation accuracy | > 85% first attempt | Validation pass rate | Dashboard, weekly |
| SQL execution success | > 95% | Execution error rate | Dashboard, daily |
| Query cache hit rate | > 30% | Cache middleware | Dashboard, daily |
| Query timeout rate | < 1% | Timeout / total | Dashboard, daily |
| Query retry rate | < 5% | Retry / total | Dashboard, daily |

### 13.2 GPU KPIs

| KPI | Target | Measurement | Reporting |
|-----|--------|-------------|-----------|
| GPU utilization (avg) | 60-80% | DCGM exporter | Dashboard, daily |
| GPU memory utilization | < 90% | DCGM exporter | Dashboard, daily |
| First token latency | < 200ms (SQLCoder), < 1s (DSv3) | vLLM metrics | Dashboard, daily |
| Token throughput | > 2000 tok/s (SQLCoder), > 500 tok/s (DSv3) | vLLM metrics | Dashboard, daily |
| Request queue depth | < 50 avg | vLLM metrics | Dashboard, real-time |
| Queue wait time | < 500ms P50, < 2s P99 | vLLM metrics | Dashboard, daily |
| Batch size | > 4 avg | vLLM metrics | Dashboard, daily |
| GPU power draw | < 80% TDP | DCGM exporter | Dashboard, weekly |

### 13.3 Infrastructure KPIs

| KPI | Target | Measurement | Reporting |
|-----|--------|-------------|-----------|
| API availability (uptime) | > 99.9% | Prometheus | Dashboard, monthly |
| API error rate (5xx) | < 0.5% | Prometheus | Dashboard, real-time |
| HPA scaling latency | < 30s | Kubernetes events | Dashboard, weekly |
| Pod startup time | < 15s (CPU), < 60s (GPU) | Kubernetes events | Dashboard, weekly |
| Node pool scaling time | < 5 min | Cluster autoscaler log | Dashboard, weekly |
| Database connection pool | < 80% utilization | PgBouncer metrics | Dashboard, daily |
| Redis cache hit rate | > 80% | Redis INFO | Dashboard, daily |
| TLS handshake time | < 100ms P99 | Ingress metrics | Dashboard, weekly |

### 13.4 Business KPIs (Performance-Adjacent)

| KPI | Target | Measurement | Reporting |
|-----|--------|-------------|-----------|
| Queries per day (QPD) | > 100K (at scale) | API counters | Dashboard, daily |
| Active users (DAU) | > 1K (at scale) | Auth events | Dashboard, daily |
| Cost per query | < $0.005 weighted avg | Cost allocation | Dashboard, weekly |
| Cost per user | < $10/mo | Cost allocation | Dashboard, monthly |
| Infrastructure cost as % of revenue | < 30% | Finance report | Monthly |
| GPU cost as % of infra cost | < 50% | Finance report | Monthly |

---

## 14. Optimization Roadmap

### 14.1 Phase 1: Quick Wins (Month 1)

| Optimization | Impact | Effort | Risk | Owner |
|-------------|--------|--------|------|-------|
| Redis cache for schema data | 50ms -> 5ms (10x) | 2 days | Low | Backend |
| PostgreSQL connection pooling (PgBouncer) | Reduce idle connections 80% | 1 day | Low | Backend |
| Response compression (gzip) | Reduce bandwidth 70% | 0.5 day | Low | Backend |
| TLS session resumption | Reduce handshake 30ms | 1 day | Low | Infra |
| Loki log compression | Reduce storage 50% | 0.5 day | Low | Infra |
| Qdrant payload on_disk | Reduce RAM 40% | 1 day | Low | Infra |
| k6 baseline load test | Identify bottlenecks | 3 days | Low | QA |

### 14.2 Phase 2: Core Optimization (Month 2)

| Optimization | Impact | Effort | Risk | Owner |
|-------------|--------|--------|------|-------|
| Connection keep-alive optimization | Reduce latency 10ms | 3 days | Low | Backend |
| Prometheus Adapter + GPU HPA | Dynamic GPU scaling | 5 days | Medium | Infra |
| Query result streaming | < 2s TTFB | 5 days | Medium | Backend |
| SQL generation caching (exact match) | 20% query reduction | 3 days | Low | Backend |
| PostgreSQL table partitioning | 30% query improvement | 5 days | Low | Backend |
| DeepSeek-V3 quantization (FP8 -> INT4) | 50% memory reduction | 5 days | Medium | ML |
| Embedding batch processing | 10x throughput | 3 days | Low | Backend |

### 14.3 Phase 3: Advanced Optimization (Month 3-4)

| Optimization | Impact | Effort | Risk | Owner |
|-------------|--------|--------|------|-------|
| vLLM continuous batching tuning | 20% throughput increase | 5 days | Medium | ML |
| GPU kernel fusion | 15% latency reduction | 10 days | High | ML |
| Query result pagination optimization | 40% response reduction | 5 days | Medium | Backend |
| Redis cluster mode (sharding) | 10x throughput | 5 days | Medium | Infra |
| PostgreSQL read replicas | 50% read query improvement | 5 days | Low | Backend |
| KEDA event-driven scaling | 30% cost reduction | 5 days | Medium | Infra |
| Adaptive model routing (ML-based) | 10% cost reduction | 10 days | High | ML |

### 14.4 Phase 4: Proactive Optimization (Month 5-6)

| Optimization | Impact | Effort | Risk | Owner |
|-------------|--------|--------|------|-------|
| Predictive auto-scaling (ML) | 20% cost reduction | 15 days | High | ML |
| Query result caching (semantic) | 40% cache hit rate | 10 days | High | Backend |
| Multi-region read replicas | 30% latency improvement | 10 days | High | Infra |
| Adaptive batch sizing | 15% GPU improvement | 5 days | Medium | ML |
| Speculative SQL generation | 10% latency improvement | 10 days | High | ML |
| Self-tuning database knobs | 20% DB improvement | 15 days | High | Backend |

---

## 15. Cost Dashboards

### 15.1 Real-Time Cost Dashboard

```
Dashboard: Query Cost
  - Cost per query (rolling 1h)
  - Cost per model tier
  - Cost per tenant
  - Cost per database type
  - GPU cost breakdown
  - Cache savings
  - Escalation cost
  - Average revenue per query (ARPQ)

Dashboard: Infrastructure Cost
  - Total monthly cost
  - Cost by service
  - Cost by namespace
  - Cost by node pool
  - Storage cost breakdown
  - Network cost breakdown
  - GPU cost vs CPU cost
  - Cost forecast (30d)

Dashboard: Efficiency
  - Cost per query trend (7d, 30d)
  - Queries per dollar
  - GPU utilization vs cost
  - Cache hit rate vs cost saved
  - Optimization ROI tracker
```

### 15.2 Cost Alerting Rules

| Alert | Threshold | Action |
|-------|-----------|--------|
| Cost per query spike | > $0.02 per query, sustained 10 min | Page on-call engineer |
| Cost per tenant spike | > $50/mo per tenant | Investigate tenant usage pattern |
| GPU cost overrun | > 150% of budgeted | Adjust routing, review pricing |
| Model cost anomaly | > 200% of baseline | Check for edge case escalation loop |
| Cache effectiveness drop | Hit rate < 50%, sustained 30 min | Investigate cache eviction or miss pattern |

### 15.3 Weekly Cost Review

```
Template: Cost Review (Weekly, every Monday)

1. Last week cost vs budget
2. Top 5 most expensive tenants
3. Top 5 most expensive queries
4. GPU utilization summary
5. Optimization progress
6. Escalation patterns
7. Anomalous cost events
8. Forecast vs actual
9. Action items
```

---

## 16. Margin Analysis

### 16.1 Per-Query Margin

| Tier | Price (per query) | Cost (weighted) | Gross Margin | Breakeven QPD |
|------|------------------|----------------|-------------|--------------|
| Starter | $0.25 | $0.0036 | 98.6% | 100 |
| Pro | $0.15 | $0.0036 | 97.6% | 500 |
| Enterprise | Custom | $0.0036 | Negotiated | Custom |

### 16.2 Per-Tenant Margin

| Tier | Monthly Price | Avg Queries | Avg Cost | Gross Margin | Monthly Revenue | Monthly Cost |
|------|--------------|-------------|----------|-------------|----------------|-------------|
| Starter | $99 | 500 | $1.80 | ~98.2% | $99 | $1.80 |
| Pro | $499 | 3,000 | $10.80 | ~97.8% | $499 | $10.80 |
| Enterprise | $2,500+ | 10,000+ | $36.00+ | ~98.6% | $2,500+ | $36.00+ |

### 16.3 Infrastructure Margin by Scale

| Stage | Tenants | Monthly Revenue | Monthly Infra Cost | Infra % of Revenue | Net Infra Margin |
|-------|---------|----------------|-------------------|-------------------|-----------------|
| Launch | 10 | $5,000 | $3,000 | 60% | 40% |
| Growth | 100 | $50,000 | $20,200 | 40% | 60% |
| Scale | 1,000 | $500,000 | $95,000 | 19% | 81% |
| Enterprise | 5,000 | $2,500,000+ | $235,000 | 9.4% | 90.6% |
| Global | 10,000 | $5,000,000+ | $350,000 | 7% | 93% |

### 16.4 Cost Reduction Levers by Impact

| Lever | Current Cost | Optimized Cost | Savings | Timeline | Effort |
|-------|-------------|---------------|---------|----------|--------|
| Cache optimization | $0.0036 -> $0.0029 | 19% | $0.0007/query | Month 1 | 3 days |
| Model routing (ML) | $0.0029 -> $0.0023 | 21% | $0.0006/query | Month 3 | 15 days |
| Batch optimization | $0.0023 -> $0.0020 | 13% | $0.0003/query | Month 2 | 5 days |
| Quantization | $0.0020 -> $0.0017 | 15% | $0.0003/query | Month 2 | 5 days |
| Semantic caching | $0.0017 -> $0.0014 | 18% | $0.0003/query | Month 4 | 10 days |
| **Total optimized** | **$0.0036 -> $0.0014** | **~61%** | **$0.0022/query** | **Month 4** | **~38 days** |

### 16.5 Breakeven Analysis

| Scenario | Month to Breakeven | Notes |
|----------|-------------------|-------|
| Worst case (10 tenants, 500 QPD) | Month 18 | High infra per tenant |
| Expected (100 tenants, 50K QPD) | Month 8 | Steady growth |
| Best case (500 tenants, 250K QPD) | Month 4 | Rapid adoption |
| Enterprise (5K tenants, 10K QPD) | Month 2 | Large initial customers |

---

## Appendix A: Performance Specification Cross-References

| Performance Topic | Related Specs |
|-----------------|---------------|
| GPU scheduling | Infrastructure-Specification.md §12 GPU Scheduling |
| Cache architecture | API-Specification.md §15 Rate Limiting & Caching |
| Queue management | API-Specification.md §14.3 Async Job Lifecycle |
| Cost allocation | Cost-Budgets.md (§1-5), API-Specification.md §10.7 |
| Model routing | AI-Agent-Specification.md §9 Model Tier Architecture |
| Database latency | Database-Specification.md §14 Performance Schema & Monitoring |
| Observability | Observability-Specification.md (§3-7) |
| Scaling strategy | Deployment-Specification.md (§15 Scaling Plan) |
| Load testing | Implementation-Plan.md EP-007 (System Integration & Testing) |
| Query latency budget | Performance-Budgets.md (§2 Latency Budgets per Stage) |
| Knowledge Engine latency | KnowledgeEngine-Specification.md §13 Testing, §14 Sequence Diagrams |

## Appendix B: Performance Metrics Glossary

| Term | Definition | Measurement |
|------|------------|-------------|
| P50 | 50th percentile latency | The median request time |
| P95 | 95th percentile latency | 95% of requests faster than this |
| P99 | 99th percentile latency | 99% of requests faster than this |
| QPD | Queries per day | Number of SQL queries generated |
| TTFB | Time to first byte | Time from request to first response byte |
| GPU utilization | Percentage of GPU compute capacity used | DCGM metrics |
| Cache hit rate | Percentage of requests served from cache | Cache middleware stats |
| Escalation rate | Percentage of queries requiring model upgrade | Router metrics |
| Gross margin | (Revenue - Cost) / Revenue | Financial calculation |
| Infra % of revenue | Infrastructure cost / total revenue | Financial calculation |

## Appendix C: Performance Test Data Requirements

| Data Type | Source | Volume | Format | Access |
|-----------|--------|--------|--------|--------|
| Anonymized queries | Production | 10K-100K | JSON Lines | Internal test environment |
| Enterprise schema dumps | Open-source datasets | 50-500 schemas | SQL DDL | Public (Northwind, StackOverflow, etc.) |
| Load test results | CI/CD | Per run | JSON | Test artifacts |
| GPU profiling data | Development | Per model | CSV | Developer workstations |
| Cost allocation data | Cloud billing API | Monthly | CSV | Finance team |
| Benchmark queries | Spider 2.0 / BIRD | 5K+ | JSON | Public benchmark suites |

## Appendix D: Performance Specification Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-07-10 | System | Initial specification — latency budgets, GPU utilization, cache strategy, cost per query, model routing, embedding cost, storage cost, queue latency, API latency, scaling strategy, load/stress testing, KPIs, optimization roadmap, cost dashboards, margin analysis |

---
*End of Performance-Specification.md — Part 1 (Sections 1-4), Part 2 (Sections 5-10), Part 3 (Sections 11-16 plus Appendices A-D)*
