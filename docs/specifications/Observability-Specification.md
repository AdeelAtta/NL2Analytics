# Observability Specification

**Enterprise Data Intelligence Platform — Unified Observability Strategy**

| Metadata | Value |
|----------|-------|
| **Author** | Principal Site Reliability Engineer |
| **Date** | 2026-07-10 |
| **Status** | Approved |
| **Version** | 1.0 |
| **Architecture Reference** | System-Architecture.md §8, Infrastructure-Specification.md §8-10 |
| **Cross-References** | AI-Agent-Specification.md, Planner-Specification.md §18, Retriever-Specification.md §19, KnowledgeEngine-Specification.md §14, Performance-Specification.md §13, §15, API-Specification.md §7, Database-Specification.md §10, ModelRouter-Specification.md §18 |

---

## Table of Contents

1. [Observability Philosophy](#1-observability-philosophy)
2. [Three Pillars Architecture](#2-three-pillars-architecture)
3. [Service-Level Indicators (SLIs)](#3-service-level-indicators-slis)
4. [Service-Level Objectives (SLOs)](#4-service-level-objectives-slos)
5. [Service-Level Agreements (SLAs)](#5-service-level-agreements-slas)
6. [Metrics Strategy](#6-metrics-strategy)
7. [Logging Strategy](#7-logging-strategy)
8. [Distributed Tracing Strategy](#8-distributed-tracing-strategy)
9. [OpenTelemetry Implementation](#9-opentelemetry-implementation)
10. [Prometheus Configuration](#10-prometheus-configuration)
11. [Grafana Strategy](#11-grafana-strategy)
12. [Alerting Strategy](#12-alerting-strategy)
13. [AI Agent Metrics](#13-ai-agent-metrics)
14. [Knowledge Engine Metrics](#14-knowledge-engine-metrics)
15. [Planner Metrics](#15-planner-metrics)
16. [Retriever Metrics](#16-retriever-metrics)
17. [Model Router Metrics](#17-model-router-metrics)
18. [API Metrics](#18-api-metrics)
19. [Infrastructure Metrics](#19-infrastructure-metrics)
20. [GPU Metrics](#20-gpu-metrics)
21. [Cost Metrics](#21-cost-metrics)
22. [Business Metrics](#22-business-metrics)
23. [SLO Burn Rate Alerting](#23-slo-burn-rate-alerting)
24. [Incident Response](#24-incident-response)
25. [Observability Testing](#25-observability-testing)
26. [Operational Playbooks](#26-operational-playbooks)
27. [Observability Maturity Model](#27-observability-maturity-model)

---

## 1. Observability Philosophy

### 1.1 Principles

| Principle | Description |
|-----------|-------------|
| **RED by default** | Every service emits Rate, Errors, and Duration metrics. No service is deployed without these three. |
| **Metrics for decisions, logs for debugging, traces for relationships** | Each pillar serves a distinct purpose. Don't force one pillar to do another's job. |
| **SLO-driven operations** | Alert on SLO burn rate, not raw metric thresholds. If the SLO is healthy, don't page. |
| **Observability is a feature** | Every feature includes observability instrumentation. Not an afterthought. Not optional. |
| **Tenant-aware aggregation** | Metrics and logs carry tenant context. Operator can drill from global → tenant → query. |
| **Cost-aware observability** | Instrumentation cost is tracked and budgeted. Sampling rates adjusted based on value vs cost. |

### 1.2 Observability Stack

| Layer | Tool | Deployment | Retention |
|-------|------|-----------|-----------|
| Metrics collection | Prometheus (kube-prometheus-stack) | Helm chart, in-cluster | 30d local, 180d Thanos |
| Metrics visualization | Grafana | Helm chart, in-cluster | N/A |
| Log aggregation | Fluent Bit → Loki | DaemonSet + Helm chart | 30d hot, 90d cold (S3) |
| Distributed tracing | OpenTelemetry Collector → Tempo | Sidecar + Helm chart | 7d |
| Alert management | Alertmanager → PagerDuty + Slack | Part of Prometheus stack | N/A |
| Status page | External service | Managed | N/A |
| Uptime monitoring | External synthetic checks | Managed | N/A |

---

## 2. Three Pillars Architecture

```
                            ┌─────────────────────────┐
                            │     Grafana              │
                            │  (visualization + alert) │
                            └────┬──────┬──────┬──────┘
                                 │      │      │
                    ┌────────────┘      │      └────────────┐
                    ▼                   ▼                   ▼
            ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
            │  Prometheus  │   │    Loki      │   │    Tempo     │
            │  (metrics)   │   │    (logs)    │   │   (traces)   │
            └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
                   │                  │                   │
                   ▼                  ▼                   ▼
            ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
            │  Service     │   │  Fluent Bit  │   │   OTel       │
            │  /metrics    │   │  DaemonSet   │   │   Collector  │
            │  (port 9090) │   │  (stdout)    │   │   (sidecar)  │
            └──────────────┘   └──────────────┘   └──────────────┘
                   │                  │                   │
                   ▼                  ▼                   ▼
            ┌────────────────────────────────────────────────────┐
            │              Kubernetes Pod                        │
            │  [ke-api] [public-api] [planner] [retriever] ...   │
            │  stdout (JSON logs) + /metrics + OTel spans        │
            └────────────────────────────────────────────────────┘
```

### 2.1 Data Flow

```
Metrics:      Pod :9090/metrics → Prometheus (scrape 15s) → Grafana
Logs:         Pod stdout (JSON) → Fluent Bit (DaemonSet) → Loki → Grafana
Traces:       Pod OTel SDK → OTel Collector (sidecar) → Tempo → Grafana
```

### 2.2 Sampling Strategy

| Environment | Traces | Logs (all at DEBUG) | Metrics |
|-------------|--------|-------------------|---------|
| Dev | 100% | All | All (high-cardinality labels enabled) |
| Staging | 10% head-based | All | All (no cardinality limits) |
| Production | 1% head-based, 100% for errors (tail-based) | WARN/ERROR all, INFO sampled 10%, DEBUG off | All (cardinality-limited to tenant_id) |

---

## 3. Service-Level Indicators (SLIs)

### 3.1 Platform SLIs

| SLI | Definition | Measurement Method | Current Baseline |
|-----|-----------|-------------------|------------------|
| API availability | % of HTTP requests returning 2xx/3xx | `http_requests_total{status=~"2.*\|3.*"} / http_requests_total` | 99.97% |
| API latency P50 | Median request latency | `http_request_duration_seconds` histogram | 250ms |
| API latency P95 | 95th percentile request latency | `http_request_duration_seconds` histogram | 1.2s |
| API latency P99 | 99th percentile request latency | `http_request_duration_seconds` histogram | 3.5s |
| Query success rate | % of NL2SQL queries returning valid results | `pipeline_query_count{status="success"} / pipeline_query_count` | 94% |
| Query latency P50 | Median end-to-end NL2SQL query time | `pipeline_total_duration` histogram | 2.1s |
| Query latency P95 | 95th percentile end-to-end query time | `pipeline_total_duration` histogram | 5.8s |
| Query latency P99 | 99th percentile end-to-end query time | `pipeline_total_duration` histogram | 7.9s |

### 3.2 Component SLIs

| SLI | Definition | Target | Measurement |
|-----|-----------|--------|-------------|
| KE API availability | % of KE API requests succeeding | 99.99% | `ke_store_operation_count{status="success"} / ke_store_operation_count` |
| KE API latency P95 | Knowledge Engine operation latency | < 50ms | `ke_store_operation_duration_ms` histogram |
| Intent classification accuracy | % of intents classified correctly | > 95% | `agent.intent.accuracy` gauge |
| Intent classification latency P50 | Intent agent processing time | < 100ms | `agent.intent.latency_ms` histogram |
| Retrieval recall@10 | % of relevant context in top 10 results | > 85% | `retriever_recall_at_10` gauge |
| Retrieval latency P95 | End-to-end retrieval time | < 550ms | `retriever_duration_ms` histogram |
| Planning feasibility rate | % of queries with feasible plan generated | > 95% | `planner_queries_total{feasible=true} / planner_queries_total` |
| Planning latency P50 | Plan generation time | < 400ms | `planner_duration_seconds` histogram |
| SQL generation parseable rate | % of SQL candidates that parse correctly | > 95% | `agent.generator.parseable_rate` gauge |
| SQL generation latency P50 (simple) | SQL generation for simple queries | < 800ms | `agent.generator.latency_ms` histogram |
| Validation pass rate | % of SQL passing validation | > 90% | `agent.validator.pass_rate` gauge |
| Policy enforcement pass rate | % of queries passing all 10 policy layers | > 97% | `pipeline_policy_result{result="pass"} / pipeline_policy_result` |
| Schema sync success rate | % of scheduled schema syncs completing | > 99% | `extraction.success_rate` counter |
| Learning cycle success rate | % of learning cycles completing | > 99% | `agent.learning.ke_write_success_rate` gauge |
| Router decision latency P99 | Model router decision time | < 10ms | `router.decision_latency_ms` histogram |
| Router fallback rate | % of queries requiring model fallback | < 5% | `router.fallback_rate` counter |

### 3.3 Infrastructure SLIs

| SLI | Definition | Target | Measurement |
|-----|-----------|--------|-------------|
| Pod availability | % of desired pods in Ready state | > 99.9% | `kube_deployment_status_replicas_ready / kube_deployment_status_replicas` |
| GPU utilization | Average GPU compute utilization | 70-85% | `rocm_smi_utilization` gauge |
| Database availability | PostgreSQL accepts connections | 99.995% | `pg_up` metric |
| Database query latency P95 | Database query time | < 10ms | `pg_stat_activity_max_query_duration` |
| Qdrant availability | Qdrant cluster healthy | 99.9% | `qdrant_grpc_status` gauge |

---

## 4. Service-Level Objectives (SLOs)

### 4.1 Platform SLOs

| SLO | Target | Window | Burn Rate Alert (2h) | Burn Rate Alert (6h) |
|-----|--------|--------|---------------------|---------------------|
| API availability | 99.9% | 30d rolling | > 14.4 min error budget consumed in 2h | > 43.2 min consumed in 6h |
| Query success rate | 95% | 7d rolling | > 3.6% of queries failing in 2h | > 10.8% failing in 6h |
| Query latency P95 | < 8s | 7d rolling | > 0.5% of queries exceeding 8s in 2h | > 1.5% exceeding in 6h |
| Policy enforcement pass rate | 97% | 30d rolling | > 2% policy failures in 2h | > 6% failures in 6h |

### 4.2 Component SLOs

| SLO | Target | Window | Burn Rate Alert |
|-----|--------|--------|-----------------|
| KE API latency P95 < 50ms | 99.9% | 30d | 2h |
| Intent classification accuracy | 95% | 7d | 1h |
| Retrieval recall@10 | 85% | 7d | 2h |
| Planning feasibility | 95% | 7d | 2h |
| Schema sync success | 99% | 30d | 4h |
| Learning cycle success | 99% | 30d | 4h |
| Router fallback rate < 5% | 99% | 7d | 2h |

### 4.3 SLO Calculation Method

```
SLO = 1 - (error_budget_consumed / total_error_budget)

Error budget = (1 - SLO_target) * total_requests_in_window

Burn rate = error_budget_consumed / (window_duration * (1 - SLO_target))

If burn rate > 1: SLO is being violated
If burn rate > 2 for 2h: Page (fast burn)
If burn rate > 1 for 6h: Page (slow burn)
If burn rate > 0.5 for 24h: Warning (impending violation)
```

---

## 5. Service-Level Agreements (SLAs)

| Tier | API Uptime | Query Success | Support Response | Reporting |
|------|-----------|---------------|------------------|-----------|
| Free | 99.0% | — | Best effort | None |
| Starter | 99.5% | 90% | 8h business hours | Monthly report |
| Pro | 99.9% | 95% | 2h business hours | Weekly report |
| Enterprise | 99.95% | 98% | 30min 24/7 | Real-time dashboard |

---

## 6. Metrics Strategy

### 6.1 Metric Naming Convention

```
# Pattern
{domain}_{subsystem}_{metric_name}{_unit}

# Examples
ke_store_operation_duration_ms
agent_intent_latency_ms
pipeline_query_count_total
router_decision_latency_ms
infra_gpu_utilization_percent
business_dau_total
```

### 6.2 Standard Metric Dimensions (All Services)

| Label | Cardinality | Source | Example |
|-------|-------------|--------|---------|
| `service` | Low (10) | Metadata | `ke-api` |
| `environment` | Low (3) | Metadata | `production` |
| `tenant_id` | High (10K) | Request context | `tnt_001` |
| `request_id` | Very high | Request context | `req_abc123` |

High-cardinality labels (tenant_id, request_id) are used in traces and logs, but **not** in Prometheus metrics. Prometheus metrics use aggregated dimensions only.

### 6.3 Standard Prometheus Metrics (All Services)

| Metric | Type | Description |
|--------|------|-------------|
| `http_requests_total` | Counter | Total HTTP requests (labels: service, method, path, status) |
| `http_request_duration_seconds` | Histogram | Request latency buckets (labels: service, method, path) |
| `http_requests_in_flight` | Gauge | Current concurrent requests |
| `service_health` | Gauge | 1=healthy, 0=unhealthy |
| `service_info` | Info | Version, commit, build timestamp |
| `service_start_time_seconds` | Gauge | Unix timestamp of last start |

### 6.4 Metrics Retention

| Granularity | Storage | Retention | Downsampled To |
|-------------|---------|-----------|----------------|
| Raw (15s scrape) | Prometheus TSDB | 30 days | — |
| 5m averages | Thanos (S3) | 180 days | Raw |
| 1h averages | Thanos (S3) | 2 years | 5m |
| Daily aggregates | PostgreSQL (metrics_store) | 3 years | 1h |

### 6.5 Metrics Storage (PostgreSQL)

All metrics are also written to the Knowledge Engine metrics store for tenant-facing dashboards and billing:

```sql
-- Database-Specification.md §10 — metrics_store.metrics
-- Used for: tenant-facing dashboards, billing, query history, cost allocation
INSERT INTO metrics_store.metrics (tenant_id, metric_name, value, tags, recorded_at)
VALUES ('tnt_001', 'query_count', 42, '{"model_tier":"simple"}', NOW());
```

This is distinct from Prometheus metrics which are for **operational** use. The PostgreSQL metrics store is for **business** use (tenant dashboards, billing, historical queries).

---

## 7. Logging Strategy

### 7.1 Log Format

All services emit structured JSON logs to stdout. Fluent Bit collects and forwards to Loki.

```json
{
  "timestamp": "2026-07-10T10:00:00.123Z",
  "level": "INFO",
  "service": "ke-api",
  "request_id": "req_abc123",
  "tenant_id": "tnt_001",
  "trace_id": "trc_001",
  "span_id": "spn_002",
  "message": "Schema store read completed",
  "logger": "ke.stores.schema",
  "caller": "schema.py:42",
  "duration_ms": 15,
  "error": null,
  "metadata": {
    "schema_id": "sch_001",
    "table_count": 25,
    "cache_hit": true
  }
}
```

### 7.2 Log Levels

| Level | Usage | Production Behavior |
|-------|-------|---------------------|
| ERROR | Service cannot fulfill request. DB unreachable, auth failure, policy enforcement violation, LLM timeout. | Always collected |
| WARN | Degraded but operational. Slow query, cache miss, rate limit approaching, fallback used. | Always collected |
| INFO | Normal operational events. Query started/completed, sync completed, feedback processed, deployment event. | Sampled 10% |
| DEBUG | Development troubleshooting. SQL generated, embedding computed, cache check, prompt sent to LLM. | Off in production |

### 7.3 Log Retention

| Environment | Hot (Loki) | Cold (S3) | Audit (S3) |
|-------------|-----------|-----------|------------|
| Dev | 1 day | None | None |
| Staging | 7 days | 30 days | 90 days |
| Production | 30 days | 90 days | 365 days |

### 7.4 Log Correlation

Every log line carries `request_id`, `trace_id`, and `span_id` — enabling navigation from log → trace → metrics.

```python
# Python: structlog configuration
import structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=structlog.threadlocal.wrap_dict(dict),
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)
```

### 7.5 Log-Based Alerting (Loki)

| Alert | Log Query | Window | Threshold |
|-------|-----------|--------|-----------|
| Error rate spike | `{service="ke-api"} |= "ERROR"` | 5m | > 10 errors/min |
| Slow query log | `{service="query-pipeline"} | json | duration_ms > 10000` | 5m | > 5 occurrences |
| Authentication failures | `{service="public-api"} |= "auth_failed"` | 5m | > 20 failures/min |
| Policy enforcement violations | `{service="query-pipeline"} |= "POLICY_BLOCKED"` | 5m | > 5 violations/min |

---

## 8. Distributed Tracing Strategy

### 8.1 Trace Structure

Every user-facing request generates a root trace with the following hierarchy:

```
Root Span: POST /v1/query
  ├── Span: api_gateway (auth, rate limit, tenant resolution)
  ├── Span: intent_agent (classify intent, extract entities, estimate complexity)
  │   ├── Span: llm_inference (if regex doesn't match)
  │   └── Event: intent_classified = {"type": "aggregate", "complexity": 0.55}
  ├── Span: model_router (select model tier)
  │   └── Event: model_selected = "qwen2.5-72b"
  ├── Span: retrieval_agent (fetch context)
  │   ├── Span: qdrant_vector_search
  │   ├── Span: bm25_keyword_search
  │   ├── Span: kg_graph_traversal
  │   ├── Span: cross_encoder_rerank
  │   └── Event: candidates = 42, tokens = 3200
  ├── Span: context_assembly (build context window)
  ├── Span: planner_agent (plan SQL approach)
  │   ├── Span: intent_classify
  │   ├── Span: query_decompose
  │   ├── Span: plan_joins
  │   ├── Span: plan_aggregations
  │   ├── Span: plan_validation
  │   └── Event: plan_accepted = true, steps = 4
  ├── Span: generator_agent (generate SQL)
  │   ├── Span: llm_inference (Qwen2.5-72B)
  │   └── Event: sql_generated = "SELECT ..."
  ├── Span: validator_agent (validate SQL)
  │   ├── Span: syntax_check
  │   ├── Span: schema_check
  │   └── Event: valid = true
  ├── Span: policy_enforcement (10 layers)
  │   ├── Span: intent_guard
  │   ├── Span: sanitization_guard
  │   ├── Span: rbac_guard
  │   ├── Span: cost_ceiling_guard
  │   ├── Span: sql_validation_guard
  │   ├── Span: read_only_guard
  │   └── Span: audit_guard
  ├── Span: executor (run SQL against target DB)
  │   ├── Span: target_db_query
  │   └── Event: row_count = 42, duration_ms = 350
  └── Span: response_format (format results)
      └── Event: response_size_bytes = 12000
```

### 8.2 Span Attributes

Every span includes these standard attributes:

| Attribute | Example | Source |
|-----------|---------|--------|
| `service.name` | `planner-agent` | Environment variable |
| `service.version` | `1.0.0` | Build metadata |
| `deployment.environment` | `production` | Environment variable |
| `tenant.id` | `tnt_001` | Request context |
| `query.id` | `qry_001` | Request context |

Agent-specific spans include additional attributes defined in each agent's observability section (AI-Agent-Specification.md §2-9).

### 8.3 Trace Sampling

| Environment | Rate | Strategy | Exceptions |
|-------------|------|----------|------------|
| Dev | 100% | Head-based (always sample) | None |
| Staging | 10% | Head-based (probabilistic) | Errors always sampled |
| Production | 1% | Head-based (probabilistic) | Errors 100% (tail-based) |
| Production (Enterprise tenants) | 10% | Head-based | Errors 100% |

### 8.4 Trace Storage

| Store | Retention | Storage Used (prod) |
|-------|-----------|-------------------|
| Tempo (hot) | 7 days | ~100GB |
| S3 (cold) | 30 days | ~300GB |

---

## 9. OpenTelemetry Implementation

### 9.1 SDK Configuration

```python
# lib/telemetry/init.py
from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION, DEPLOYMENT_ENVIRONMENT
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

def init_telemetry(service_name: str, service_version: str, env: str):
    resource = Resource.create({
        SERVICE_NAME: service_name,
        SERVICE_VERSION: service_version,
        DEPLOYMENT_ENVIRONMENT: env,
    })

    # Tracing
    trace_provider = TracerProvider(resource=resource)
    trace_exporter = OTLPSpanExporter(endpoint="http://otel-collector:4317")
    trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    trace.set_tracer_provider(trace_provider)

    # Metrics
    metric_exporter = OTLPMetricExporter(endpoint="http://otel-collector:4317")
    metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_ms=15000)
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    return trace.get_tracer(service_name), metrics.get_meter(service_name)
```

### 9.2 OTel Collector Configuration

```yaml
# infra/charts/opencode/templates/otel-collector.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 1s
    send_batch_size: 1024
  memory_limiter:
    check_interval: 1s
    limit_mib: 500
  attributes:
    actions:
      - key: environment
        value: production
        action: upsert
  probabilistic_sampler:
    hash_seed: 42
    sampling_percentage: 1.0  # Production: 1%

exporters:
  otlp:
    endpoint: tempo.monitoring:4317
    tls:
      insecure: true
  prometheus:
    endpoint: 0.0.0.0:8889
    namespace: otel
  debug:
    verbosity: basic

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, attributes, probabilistic_sampler, batch]
      exporters: [otlp, debug]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [prometheus, debug]
```

### 9.3 FastAPI Middleware

```python
# lib/telemetry/middleware.py
from opentelemetry import trace
from opentelemetry.propagate import extract
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

def instrument_app(app, service_name: str):
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=trace.get_tracer_provider(),
        meter_provider=metrics.get_meter_provider(),
        excluded_urls="/health,/ready,/metrics",
        server_request_hook=lambda span, scope: span.set_attribute(
            "tenant.id", scope.get("headers", {}).get("x-tenant-id", b"unknown").decode()
        ),
    )
```

---

## 10. Prometheus Configuration

### 10.1 Prometheus Operator

Prometheus is deployed via kube-prometheus-stack Helm chart with custom configuration:

```yaml
# infra/charts/opencode/values/prometheus.yaml
prometheus:
  prometheusSpec:
    scrapeInterval: 15s
    evaluationInterval: 15s
    retention: 30d
    retentionSize: 50GB
    resources:
      requests: { cpu: "500m", memory: "2Gi" }
      limits: { cpu: "2", memory: "8Gi" }
    additionalScrapeConfigs:
      - job_name: opencode-services
        kubernetes_sd_configs:
          - role: pod
        relabel_configs:
          - source_labels: [__meta_kubernetes_pod_label_app_kubernetes_io_part_of]
            action: keep
            regex: opencode
          - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
            action: keep
            regex: "true"
          - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
            action: replace
            regex: ([^:]+)(?::\d+)?;(\d+)
            replacement: $1:$2
            target_label: __address__
    thanos:
      objectStorageConfig:
        key: thanos.yaml
        name: thanos-objectstorage
```

### 10.2 ServiceMonitor Template

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: {{ .Values.service.name }}
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: {{ .Values.service.name }}
  endpoints:
    - port: metrics
      interval: 15s
      scrapeTimeout: 10s
      path: /metrics
  namespaceSelector:
    matchNames:
      - opencode
```

### 10.3 Prometheus Recording Rules

```yaml
groups:
  - name: opencode-platform
    interval: 1m
    rules:
      - record: job:http_requests_total:rate5m
        expr: sum(rate(http_requests_total[5m])) by (service)
      - record: job:http_request_duration_p95:rate5m
        expr: histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service))
      - record: job:error_rate:rate5m
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
          /
          sum(rate(http_requests_total[5m])) by (service)

  - name: opencode-query-pipeline
    interval: 1m
    rules:
      - record: job:pipeline_query_success_rate:rate5m
        expr: |
          sum(rate(pipeline_query_count{status="success"}[5m]))
          /
          sum(rate(pipeline_query_count[5m]))
      - record: job:policy_pass_rate:rate5m
        expr: |
          sum(rate(pipeline_policy_result{result="pass"}[5m]))
          /
          sum(rate(pipeline_policy_result[5m]))
```

---

## 11. Grafana Strategy

### 11.1 Datasources

| Datasource | Type | URL | Access |
|-----------|------|-----|--------|
| Prometheus | prometheus | http://prometheus-operated:9090 | In-cluster |
| Loki | grafana-loki | http://loki:3100 | In-cluster |
| Tempo | tempo | http://tempo:3200 | In-cluster |
| CloudWatch | AWS | Custom | IAM role |

### 11.2 Dashboard Hierarchy

```
Grafana
├── Platform (top-level, all-hands)
│   ├── Executive Summary      — DAU, revenue, cost per query, uptime, SLO health
│   ├── Cost Dashboard          — Daily inference cost, GPU cost, cost per tenant tier
│   └── SLO Dashboard           — Burn rate, error budget remaining, SLO status per tier
├── Operations (on-call, SRE)
│   ├── Service Overview        — Request rate, error rate, latency per service
│   ├── Query Pipeline          — Query volume, stage breakdown, model router decisions
│   ├── Infrastructure          — Cluster health, node resources, HPA status, PG/Qdrant
│   └── Deployments             — Rolling update progress, rollback rate, canary health
├── Component (per service)
│   ├── KE API                  — Store latency, cache hit ratio, tenant count
│   ├── Intent Agent            — Accuracy, confidence, latency, model tier distribution
│   ├── Retriever               — Recall, precision, phase latency, cache hit ratio
│   ├── Planner                 — Feasibility rate, join accuracy, plan cache hit ratio
│   ├── Generator               — Parseable rate, retry rate, tier distribution
│   ├── Validator               — Pass rate, false positive rate, schema lookup count
│   ├── Model Router            — Decision latency, cost per query, fallback rate
│   └── Learning Loop           — Feedback rate, cycle duration, Q&A pair creation
├── Infrastructure (deep dive)
│   ├── GPU Dashboard           — Utilization, memory, power, KV cache, model load time
│   ├── PostgreSQL              — Connections, query latency, WAL rate, replication lag
│   ├── Qdrant                  — Query latency, collection size, segment count
│   └── K8s Cluster             — Node resources, pod count, network, HPA status
└── Business (customer-facing)
    ├── Tenant Dashboard        — Per-tenant query volume, success rate, latency, cost
    ├── Usage Dashboard         — DAU, WAU, MAU, queries per user, queries by domain
    └── Billing Dashboard       — Cost per tenant, tier allocation, invoice preview
```

### 11.3 Dashboard Conventions

| Convention | Standard |
|-----------|----------|
| Refresh interval | 30s for ops dashboards, 5m for business dashboards |
| Time range default | Last 1h for ops, last 7d for business |
| Color scheme | Green = healthy, Yellow = warning, Red = critical, Gray = no data |
| Template variables | `$service`, `$tenant`, `$model_tier`, `$environment` |
| Annotations | Deployments marked on all dashboards |
| Links | Cross-dashboard links (Service Overview → Query Pipeline) |

### 11.4 Key Dashboard JSON (Service Overview)

```json
{
  "dashboard": "Service Overview",
  "panels": [
    {
      "title": "Request Rate",
      "type": "timeseries",
      "targets": [{
        "expr": "sum(rate(http_requests_total[5m])) by (service)",
        "legendFormat": "{{ service }}"
      }]
    },
    {
      "title": "Error Rate",
      "type": "timeseries",
      "targets": [{
        "expr": "sum(rate(http_requests_total{status=~\"5..\"}[5m])) / sum(rate(http_requests_total[5m]))",
        "legendFormat": "Error rate"
      }]
    },
    {
      "title": "Latency P50/P95/P99",
      "type": "timeseries",
      "targets": [
        { "expr": "histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))", "legendFormat": "P50" },
        { "expr": "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))", "legendFormat": "P95" },
        { "expr": "histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))", "legendFormat": "P99" }
      ]
    },
    {
      "title": "CPU/Memory per Service",
      "type": "timeseries",
      "targets": [
        { "expr": "sum(container_cpu_usage_seconds_total) by (pod)", "legendFormat": "{{ pod }}" }
      ]
    }
  ]
}
```

---

## 12. Alerting Strategy

### 12.1 Alert Severity Levels

| Severity | Response Time | Channel | Examples |
|----------|--------------|---------|----------|
| **Critical** | < 5 min | PagerDuty + Slack | Service down, SLO violation, data loss |
| **Warning** | < 30 min | Slack #alerts | High latency, error rate increase, approaching limits |
| **Info** | Next business day | Slack #low-priority | Certificate expiry, slow storage growth |

### 12.2 Alert Routing

```yaml
route:
  receiver: default
  routes:
    - match:
        severity: critical
      receiver: pagerduty-critical
      repeat_interval: 5m
      group_wait: 30s
      group_interval: 1m
    - match:
        severity: warning
      receiver: slack-warning
      repeat_interval: 30m
    - match:
        severity: info
      receiver: slack-info
      repeat_interval: 6h

receivers:
  - name: pagerduty-critical
    pagerduty_configs:
      - routing_key: <PAGERDUTY_KEY>
        severity: critical
        description: '{{ .GroupLabels.alertname }} - {{ .CommonAnnotations.description }}'
  - name: slack-warning
    slack_configs:
      - channel: "#alerts"
        title: '[{{ .Status | toUpper }}] {{ .GroupLabels.alertname }}'
        text: '{{ .CommonAnnotations.description }}'
  - name: slack-info
    slack_configs:
      - channel: "#low-priority"
        text: '{{ .CommonAnnotations.description }}'
```

### 12.3 Critical Alerts

| Alert | Condition | For | Expected Response |
|-------|-----------|-----|-------------------|
| **ServiceDown** | `service_health == 0` | 30s | Check pod status, rollback if new deployment |
| **HighErrorRate** | `job:error_rate:rate5m > 0.05` | 5m | Investigate logs, check dependencies |
| **SLOBurnRate** | SLO burn rate > 2 for 2h or > 1 for 6h | Immediate | Page on-call, investigate root cause |
| **PipelineStuck** | `rate(pipeline_query_count[5m]) == 0` | 2m | Check GPU pods, queue depth |
| **DBDown** | `pg_up == 0` | 10s | Fail over to replica, restore from backup |
| **AllGPUUnhealthy** | `count(rocm_smi_utilization > 0) == 0` | 1m | Check GPU nodes, initiate cloud fallback |
| **DataCorruption** | Multiple policy enforcement violations or validation failures | 5m | Stop queries, investigate, restore from backup |

### 12.4 Warning Alerts

| Alert | Condition | For | Expected Response |
|-------|-----------|-----|-------------------|
| **HighLatency** | `job:http_request_duration_p95:rate5m > 5` | 10m | Investigate slow queries, check DB |
| **GPUSaturation** | `avg(rocm_smi_utilization) > 0.95` | 10m | Scale GPU nodes, check for stuck requests |
| **CacheHitRatioDrop** | `rate(retriever_cache_hit_ratio[30m]) < 0.3` | 15m | Investigate cache invalidation storm |
| **RouterFallbackSpike** | `rate(router.fallback_rate[5m]) > 0.10` | 5m | Check model health, investigate routing |
| **FeedbackStall** | `rate(agent.learning.ke_write_success_rate[10m]) == 0` | 10m | Check learning loop pod |
| **ConnPoolExhaustion** | `pg_connection_count > 0.8 * pg_connection_max` | 5m | Investigate connection leaks |
| **CostAnomaly** | `avg(router.cost_per_query[1h]) > 2 * avg(router.cost_per_query[7d])` | 30m | Check for model escalation loop |
| **CertExpiry** | `avg(ssl_certificate_expiry_days) < 30` | 24h | Renew certificate |

### 12.5 Info Alerts

| Alert | Condition | For | Expected Response |
|-------|-----------|-----|-------------------|
| **StorageGrowth** | `rate(kube_node_status_capacity_bytes[30d]) > 0.2` | 30d | Review retention policies |
| **OldK8sVersion** | `kube_version_info{version !~ "1.3[01].*"}` | 7d | Plan cluster upgrade |
| **ImagePullFailures** | `rate(kube_pod_container_status_waiting_reason{reason="ImagePullBackOff"}[1h]) > 0` | 1h | Check registry credentials |

---

## 13. AI Agent Metrics

### 13.1 Intent Agent

Defined in AI-Agent-Specification.md §2.9. Key metrics:

| Metric | Type | Labels | Target |
|--------|------|--------|--------|
| `agent_intent_latency_ms` | Histogram | model_used | P50 < 100ms, P95 < 200ms |
| `agent_intent_accuracy` | Gauge | complexity | > 95% |
| `agent_intent_confidence` | Histogram | intent_type | Mean > 0.85 |
| `agent_intent_model_tier_distribution` | Counter | tier | Track distribution |
| `agent_intent_unknown_rate` | Counter | — | < 5% |
| `agent_intent_retry_count` | Counter | — | < 2% |
| `agent_intent_cost_per_query` | Histogram | — | Mean < $0.001 |

### 13.2 Retriever Agent

Defined in AI-Agent-Specification.md §3.9. Key metrics:

| Metric | Type | Labels | Target |
|--------|------|--------|--------|
| `agent_retriever_latency_ms` | Histogram | phase | P50 < 200ms, P95 < 400ms |
| `agent_retriever_precision_at_10` | Gauge | — | > 0.80 |
| `agent_retriever_recall_at_10` | Gauge | — | > 0.85 |
| `agent_retriever_candidate_counts` | Histogram | stage | Track candidate volume |
| `agent_retriever_cache_hit_rate` | Gauge | cache_layer | > 0.30 |
| `agent_retriever_context_window_usage` | Histogram | — | Mean < 70% |
| `agent_retriever_fallback_rate` | Counter | fallback_reason | < 1% |

### 13.3 Planner Agent

Defined in AI-Agent-Specification.md §4.9 and Planner-Specification.md §18. Key metrics:

| Metric | Type | Labels | Target |
|--------|------|--------|--------|
| `agent_planner_latency_ms` | Histogram | complexity | P50 < 400ms, P95 < 800ms |
| `agent_planner_feasibility_rate` | Gauge | — | > 95% |
| `agent_planner_join_accuracy` | Gauge | — | > 90% |
| `agent_planner_column_accuracy` | Gauge | — | > 95% |
| `agent_planner_retry_rate` | Counter | — | < 10% |
| `agent_planner_plan_cache_hit_rate` | Gauge | — | > 0.20 |
| `planner_reflection_count` | Histogram | — | > 2 is error |
| `planner_cost_estimate_accuracy` | Gauge | — | Within 50% |

### 13.4 Generator Agent

Defined in AI-Agent-Specification.md §5.9. Key metrics:

| Metric | Type | Labels | Target |
|--------|------|--------|--------|
| `agent_generator_latency_ms` | Histogram | model_tier | Simple P50 < 800ms, Complex P50 < 3s |
| `agent_generator_first_attempt_accuracy` | Gauge | model_tier | > 70% |
| `agent_generator_candidate_accuracy` | Gauge | — | > 85% |
| `agent_generator_parseable_rate` | Gauge | model_tier | > 95% |
| `agent_generator_retry_rate` | Counter | reason | < 15% |
| `agent_generator_tier_distribution` | Counter | tier | Track per model |

### 13.5 Validator Agent

Defined in AI-Agent-Specification.md §6.9. Key metrics:

| Metric | Type | Labels | Target |
|--------|------|--------|--------|
| `agent_validator_latency_ms` | Histogram | check_type | P50 < 100ms, P95 < 200ms |
| `agent_validator_pass_rate` | Gauge | check_type | Drift monitor |
| `agent_validator_false_positive_rate` | Gauge | — | < 0.1% |
| `agent_validator_true_positive_rate` | Gauge | — | > 99% |
| `agent_validator_schema_lookup_count` | Histogram | — | Track KE API load |

### 13.6 Reflection Agent

Defined in AI-Agent-Specification.md §7.9. Key metrics:

| Metric | Type | Labels | Target |
|--------|------|--------|--------|
| `agent_reflection_latency_ms` | Histogram | — | P50 < 500ms, P95 < 1s |
| `agent_reflection_approval_rate` | Gauge | — | > 85% |
| `agent_reflection_issue_accuracy` | Gauge | — | > 80% |
| `agent_reflection_false_positive_rate` | Gauge | — | < 10% |
| `agent_reflection_improvement_rate` | Gauge | — | > 5% |
| `agent_reflection_skipped_rate` | Counter | — | < 5% |

### 13.7 Repair Agent

Defined in AI-Agent-Specification.md §8.9. Key metrics:

| Metric | Type | Labels | Target |
|--------|------|--------|--------|
| `agent_repair_latency_ms` | Histogram | attempt | P50 < 500ms, P95 < 1s |
| `agent_repair_success_rate` | Gauge | attempt | > 80% |
| `agent_repair_overall_success_rate` | Gauge | — | > 90% |
| `agent_repair_repair_rate` | Gauge | — | Drift monitor |
| `agent_repair_change_type_distribution` | Counter | change_type | Track common fixes |
| `agent_repair_regression_rate` | Gauge | — | < 5% |

### 13.8 Learning Agent

Defined in AI-Agent-Specification.md §9.9. Key metrics:

| Metric | Type | Labels | Target |
|--------|------|--------|--------|
| `agent_learning_cycle_duration_ms` | Histogram | trigger | P95 < 30s |
| `agent_learning_feedback_per_cycle` | Gauge | — | Track volume |
| `agent_learning_validation_pass_rate` | Gauge | — | > 70% |
| `agent_learning_qa_pairs_per_cycle` | Counter | — | Track learning output |
| `agent_learning_schema_enrichments_per_cycle` | Counter | — | Track enrichment |
| `agent_learning_patterns_mined_per_cycle` | Counter | — | Track discovery |
| `agent_learning_ke_write_success_rate` | Gauge | — | > 99% |

### 13.9 Cross-Agent Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `agent_execution_count_total` | Counter | agent | Total executions per agent |
| `agent_latency_ms` | Histogram | agent | Per-agent latency |
| `agent_error_count_total` | Counter | agent, error_type | Per-agent error count |
| `agent_cost_total` | Counter | agent, model | Cumulative inference cost |

---

## 14. Knowledge Engine Metrics

Defined in KnowledgeEngine-Specification.md §14.1.

### 14.1 Store Operation Metrics

| Metric | Type | Labels | Target |
|--------|------|--------|--------|
| `ke_store_operation_duration_ms` | Histogram | store, operation, status | P50 < 10ms, P95 < 50ms |
| `ke_store_operation_count_total` | Counter | store, operation, status | Track volume |
| `ke_store_cache_hit_ratio` | Gauge | store | > 0.80 |
| `ke_store_object_count` | Gauge | store | Track growth |

### 14.2 Schema Extraction Metrics

| Metric | Type | Labels | Target |
|--------|------|--------|--------|
| `ke_extraction_duration_ms` | Histogram | connector, database_type | P95 < 30s (200 tables) |
| `ke_extraction_tables_per_second` | Gauge | connector | > 50 tables/s |
| `ke_extraction_success_rate` | Counter | connector | > 99% |
| `ke_extraction_connector_errors_total` | Counter | connector, error_type | 0 |
| `ke_extraction_schema_count` | Gauge | — | Per tenant |
| `ke_extraction_table_count` | Gauge | — | Per tenant |
| `ke_extraction_relationship_count` | Gauge | — | Per tenant |

### 14.3 Schema Enrichment Metrics

| Metric | Type | Labels | Target |
|--------|------|--------|--------|
| `ke_enrichment_tables_per_second` | Gauge | — | > 5 tables/s |
| `ke_enrichment_description_confidence` | Histogram | — | Mean > 0.80 |
| `ke_enrichment_relationship_precision` | Gauge | — | > 0.80 |
| `ke_enrichment_llm_success_rate` | Counter | model | > 95% |
| `ke_enrichment_confidence_distribution` | Histogram | — | Monitor low-confidence drift |

### 14.4 Embedding Pipeline Metrics

| Metric | Type | Labels | Target |
|--------|------|--------|--------|
| `ke_embedding_duration_ms` | Histogram | entity_type | P95 < 100ms per batch |
| `ke_embedding_count_total` | Counter | entity_type | Track volume |
| `ke_embedding_queue_depth` | Gauge | — | < 1000 |
| `ke_embedding_batch_size` | Histogram | — | Mean > 64 |

### 14.5 Context Assembly Metrics

| Metric | Type | Labels | Target |
|--------|------|--------|--------|
| `ke_context_tokens_used` | Histogram | priority | Mean < 6000 |
| `ke_context_assembly_duration_ms` | Histogram | complexity | P95 < 100ms |
| `ke_context_sources_used` | Histogram | — | Mean 3-5 |

---

## 15. Planner Metrics

Defined in Planner-Specification.md §18. Consolidated here:

| Metric | Type | Labels | Target |
|--------|------|--------|--------|
| `planner_queries_total` | Counter | type, complexity, feasible | Track volume |
| `planner_duration_seconds` | Histogram | step | P50 < 400ms, P95 < 800ms |
| `planner_step_duration_seconds` | Histogram | step | P95 < 2s (total) |
| `planner_validation_duration_seconds` | Histogram | — | P95 < 500ms |
| `planner_reflection_count` | Histogram | — | > 2 is error |
| `planner_reflection_reason_total` | Counter | reason | Track reflection triggers |
| `planner_errors_total` | Counter | error_code | > 5% alert |
| `planner_validation_errors_total` | Counter | error_code | Track by validation code |
| `planner_decomposition_count` | Histogram | — | Track sub-query count |
| `planner_join_count` | Histogram | — | Track join complexity |
| `planner_estimated_rows` | Histogram | — | Track estimate distribution |
| `planner_estimated_cost` | Histogram | — | Track cost distribution |
| `planner_tool_calls_total` | Counter | tool | Track tool usage |
| `planner_cost_estimate_accuracy` | Gauge | — | Within 50% of actual |
| `planner_memory_usage_bytes` | Gauge | — | > 100MB alerts |
| `planner_cache_hit_ratio` | Gauge | — | < 10% alerts |
| `planner_intent_accuracy` | Gauge | — | Monitored via feedback |

---

## 16. Retriever Metrics

Defined in Retriever-Specification.md §19. Consolidated here:

| Metric | Type | Labels | Target |
|--------|------|--------|--------|
| `retriever_queries_total` | Counter | modality | Track volume |
| `retriever_duration_ms` | Histogram | phase | P50 < 250ms, P95 < 550ms |
| `retriever_phase_duration_ms` | Histogram | phase | Per-phase budgets |
| `retriever_modalities_used` | Histogram | — | < 2 suggests fallback |
| `retriever_candidates_found` | Histogram | stage | < 5 suggests poor recall |
| `retriever_early_termination_rate` | Gauge | — | < 10% suggests complexity |
| `retriever_empty_results_rate` | Gauge | — | > 5% suggests recall issue |
| `retriever_fallback_rate` | Gauge | modality | > 10% suggests infra issue |
| `retriever_expansion_rate` | Gauge | — | < 20% suggests expansion underused |
| `retriever_rerank_rate` | Gauge | — | < 50% suggests reranker issue |
| `retriever_cache_hit_ratio` | Gauge | cache_layer | < 40% suggests cache issue |
| `retriever_context_compression_ratio` | Histogram | strategy | < 0.3 suggests over-compression |
| `retriever_context_tokens` | Histogram | — | > 7500 suggests budget exceeded |
| `retriever_vector_search_latency_ms` | Histogram | — | P95 < 60ms |
| `retriever_keyword_search_latency_ms` | Histogram | — | P95 < 40ms |
| `retriever_kg_traversal_latency_ms` | Histogram | — | P95 < 100ms |
| `retriever_rerank_latency_ms` | Histogram | — | P95 < 400ms |
| `retriever_embedding_latency_ms` | Histogram | — | P95 < 20ms |

### 16.1 Retriever Quality Metrics

| Metric | Type | Target |
|--------|------|--------|
| `retriever_recall_at_10` | Gauge | > 80% |
| `retriever_recall_at_30` | Gauge | > 90% |
| `retriever_precision_at_10` | Gauge | > 70% |
| `retriever_mrr` | Gauge | > 0.85 |
| `retriever_ndcg_at_10` | Gauge | > 0.75 |
| `retriever_fallout_rate` | Gauge | < 10% |
| `retriever_context_usefulness_score` | Gauge | > 3.5/5 |

---

## 17. Model Router Metrics

Defined in ModelRouter-Specification.md §18. Consolidated here:

| Metric | Type | Labels | Target |
|--------|------|--------|--------|
| `router_decision_latency_ms` | Histogram | strategy, complexity | P50 < 3ms, P99 < 10ms |
| `router_decisions_total` | Counter | model_id, intent_type, tenant_tier | Track volume |
| `router_cost_per_query` | Histogram | model_id, tenant_tier | Mean < $0.005 |
| `router_savings_vs_gpt4o_total` | Counter | tenant_tier | Track savings |
| `router_fallback_chain_length` | Histogram | — | Mean < 0.1 |
| `router_fallback_rate` | Counter | trigger_reason | < 5% |
| `router_no_capable_model_total` | Counter | — | < 1% |
| `router_cache_hit_ratio` | Gauge | — | > 30% |
| `router_model_health_status` | Gauge | model_id | 1 = healthy |
| `router_routing_accuracy` | Gauge | model_id | > 85% |

### 17.1 Inference Model Metrics

| Metric | Type | Labels | Target |
|--------|------|--------|--------|
| `model_inference_latency_ms` | Histogram | model_id | Per-model budgets |
| `model_first_token_latency_ms` | Histogram | model_id | Per-model budgets |
| `model_queue_depth` | Gauge | model_id | < max_concurrent |
| `model_gpu_utilization` | Gauge | model_id | > 70% |
| `model_error_rate` | Counter | model_id | < 2% |
| `model_invalid_sql_rate` | Counter | model_id | Per-model tracking |
| `model_accuracy` | Gauge | model_id | Per-model trend |

---

## 18. API Metrics

### 18.1 Public API Metrics

| Metric | Type | Labels | Target |
|--------|------|--------|--------|
| `api_requests_total` | Counter | method, path, status, tenant_tier | Track volume |
| `api_request_duration_seconds` | Histogram | method, path | P50 < 200ms, P95 < 1s |
| `api_requests_in_flight` | Gauge | — | Track concurrency |
| `api_request_size_bytes` | Histogram | path | Track payload sizes |
| `api_response_size_bytes` | Histogram | path | Track response sizes |
| `api_rate_limit_hits_total` | Counter | tenant_tier | Track rate limit enforcement |
| `api_auth_failures_total` | Counter | reason | Track auth failures |
| `api_tenant_active_count` | Gauge | tier | Track active tenants |

### 18.2 Internal KE API Metrics

| Metric | Type | Labels | Target |
|--------|------|--------|--------|
| `ke_api_requests_total` | Counter | store, operation | Track KE API volume |
| `ke_api_request_duration_seconds` | Histogram | store, operation | P50 < 10ms, P95 < 50ms |
| `ke_api_requests_in_flight` | Gauge | — | Track concurrency |

### 18.3 API Error Classification

```python
# Error codes that map to API metrics labels
API_ERROR_CLASSIFICATION = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    502: "bad_gateway",
    503: "service_unavailable",
    504: "gateway_timeout",
}
```

---

## 19. Infrastructure Metrics

### 19.1 Kubernetes Metrics

| Metric | Type | Labels | Source | Target |
|--------|------|--------|--------|--------|
| `kube_node_count` | Gauge | node_pool, instance_type | kube-state-metrics | Track cluster size |
| `kube_node_conditions` | Gauge | condition, node | kube-state-metrics | All healthy |
| `kube_pod_container_status_restarts_total` | Counter | pod, container | kube-state-metrics | < 3 in 7d |
| `kube_deployment_status_replicas_ready` | Gauge | deployment | kube-state-metrics | = desired replicas |
| `kube_deployment_status_replicas_unavailable` | Gauge | deployment | kube-state-metrics | 0 |
| `kube_hpa_current_replicas` | Gauge | hpa | kube-state-metrics | Track scale |
| `kube_hpa_desired_replicas` | Gauge | hpa | kube-state-metrics | Track target |
| `kube_namespace_phase` | Gauge | namespace | kube-state-metrics | Active |
| `kube_pod_resource_requests` | Gauge | resource, pod | kube-state-metrics | Track allocation |
| `kube_pod_resource_limits` | Gauge | resource, pod | kube-state-metrics | Track limits |

### 19.2 Node-Level Metrics

| Metric | Type | Labels | Source | Target |
|--------|------|--------|--------|--------|
| `node_cpu_utilization` | Gauge | node | node_exporter | < 80% |
| `node_memory_utilization` | Gauge | node | node_exporter | < 80% |
| `node_disk_usage_percent` | Gauge | device, node | node_exporter | < 80% |
| `node_disk_io_utilization` | Gauge | device, node | node_exporter | < 70% |
| `node_network_receive_bytes` | Counter | device, node | node_exporter | Track baseline |
| `node_network_transmit_bytes` | Counter | device, node | node_exporter | Track baseline |

### 19.3 PostgreSQL Metrics

| Metric | Type | Labels | Source | Target |
|--------|------|--------|--------|--------|
| `pg_up` | Gauge | server | postgres_exporter | 1 |
| `pg_connection_count` | Gauge | database | postgres_exporter | < 80% of max |
| `pg_connection_max` | Gauge | — | postgres_exporter | Track limit |
| `pg_query_latency_seconds` | Histogram | database | postgres_exporter | P95 < 10ms |
| `pg_transactions_total` | Counter | database | postgres_exporter | Track volume |
| `pg_replication_lag_bytes` | Gauge | replica | postgres_exporter | < 50MB |
| `pg_replication_lag_seconds` | Gauge | replica | postgres_exporter | < 5s |
| `pg_database_size_bytes` | Gauge | database | postgres_exporter | Track growth |
| `pg_bloat_ratio` | Gauge | table | pg_bloat_check | < 20% |
| `pg_cache_hit_ratio` | Gauge | database | postgres_exporter | > 99% |

### 19.4 Qdrant Metrics

Removed during cleanup — Qdrant metrics removed.

### 19.5 Redis Metrics

Removed during cleanup — Redis metrics removed.

---

## 20. GPU Metrics

### 20.1 AMD ROCm Metrics (via AMDC Exporter)

| Metric | Type | Labels | Target |
|--------|------|--------|--------|
| `rocm_smi_utilization` | Gauge | device, node | 70-85% |
| `rocm_smi_memory_utilization` | Gauge | device, node | 80-90% |
| `rocm_smi_memory_total_bytes` | Gauge | device, node | Track capacity |
| `rocm_smi_memory_used_bytes` | Gauge | device, node | Track usage |
| `rocm_smi_power_draw_watts` | Gauge | device, node | 70-85% of TDP |
| `rocm_smi_temperature_celsius` | Gauge | device, node | < 85C |
| `rocm_smi_pcie_bandwidth_utilization` | Gauge | device, node | < 80% |
| `rocm_smi_device_health` | Gauge | device, node | 1 = healthy |

### 20.2 Inference Server Metrics (vLLM / SGLang)

| Metric | Type | Labels | Target |
|--------|------|--------|--------|
| `vllm_request_count_total` | Counter | model | Track requests |
| `vllm_request_latency_ms` | Histogram | model | Per-model budgets |
| `vllm_first_token_latency_ms` | Histogram | model | SQLCoder P50 < 200ms |
| `vllm_token_throughput` | Gauge | model | SQLCoder > 2000 tok/s |
| `vllm_queue_depth` | Gauge | model | < 50 avg |
| `vllm_queue_wait_time_ms` | Histogram | model | P50 < 500ms |
| `vllm_batch_size` | Histogram | model | Mean > 4 |
| `vllm_kv_cache_usage_percent` | Gauge | model | 70-90% |
| `vllm_model_load_time_seconds` | Gauge | model | < 30s |
| `vllm_gpu_memory_usage_percent` | Gauge | model | 80-90% |
| `vllm_scheduler_running_batches` | Gauge | model | Track utilization |
| `vllm_scheduler_waiting_batches` | Gauge | model | 0 = healthy |

### 20.3 GPU Observability Dashboard

```
GPU Overview
├── Per-GPU Utilization       (heatmap by device × time)
├── GPU Memory Usage          (timeseries, per device)
├── GPU Temperature           (timeseries, per device)
├── GPU Power Draw            (per-device vs TDP)
├── vLLM Queue Depth          (per model)
├── First Token Latency       (P50/P95/P99 per model)
├── Token Throughput          (per model, per device)
├── KV Cache Utilization      (per model)
└── GPU Health Status         (per device, color-coded)
```

---

## 21. Cost Metrics

### 21.1 Inference Cost Metrics

| Metric | Type | Labels | Target |
|--------|------|--------|--------|
| `cost_inference_total` | Counter | model_id, tenant_tier | < budget |
| `cost_inference_per_query` | Histogram | model_id | Weighted mean < $0.0036 |
| `cost_inference_per_tenant` | Counter | tenant_id | < tier max |
| `cost_inference_accumulated` | Counter | tenant_tier, day | Track daily |

### 21.2 Infrastructure Cost Metrics

| Metric | Type | Labels | Source |
|--------|------|--------|--------|
| `cost_infrastructure_eks_total` | Counter | environment | AWS Cost Explorer |
| `cost_infrastructure_ec2_total` | Counter | node_pool | AWS Cost Explorer |
| `cost_infrastructure_gpu_total` | Counter | — | AWS Cost Explorer |
| `cost_infrastructure_storage_total` | Counter | service | AWS Cost Explorer |
| `cost_infrastructure_data_transfer` | Counter | region | AWS Cost Explorer |

### 21.3 Cost Alerting

| Alert | Condition | For | Channel |
|-------|-----------|-----|---------|
| Cost per query spike | `avg(cost_inference_per_query[10m]) > 0.02` | 10m | PagerDuty |
| Cost per tenant spike | `cost_inference_per_tenant > 50` | 24h | Slack |
| GPU cost overrun | `cost_infrastructure_gpu_total > 1.5 * budget` | 24h | Slack |
| Model cost anomaly | `rate(cost_inference_total[1h]) > 2 * rate(cost_inference_total[7d])` | 1h | Slack |
| Cache effectiveness drop | `avg(retriever_cache_hit_ratio[30m]) < 0.5` | 30m | Slack |

### 21.4 Cost Savings Tracking

```python
# Computed metric: savings vs pure GPT-4o baseline
savings_vs_gpt4o = (
    count(pipeline_query_count) * 0.02  # Cost if all queries used GPT-4o
    - cost_inference_total               # Actual inference cost
)
```

---

## 22. Business Metrics

### 22.1 Usage Metrics

| Metric | Type | Labels | Source |
|--------|------|--------|--------|
| `business_dau_total` | Gauge | tenant_tier | PostgreSQL (metrics_store) |
| `business_wau_total` | Gauge | tenant_tier | PostgreSQL (metrics_store) |
| `business_mau_total` | Gauge | tenant_tier | PostgreSQL (metrics_store) |
| `business_queries_total` | Counter | tenant_tier, domain | Pipeline events |
| `business_queries_per_user` | Histogram | — | Pipeline events |
| `business_query_success_rate` | Gauge | tenant_tier | Pipeline events |
| `business_avg_cost_per_query` | Gauge | tenant_tier | Cost metrics |
| `business_queries_by_domain` | Counter | domain | Pipeline events |
| `business_model_tier_distribution` | Counter | tier, tenant_tier | Router events |
| `business_feedback_rate` | Gauge | — | Learning events |

### 22.2 Revenue Metrics

| Metric | Type | Labels | Source |
|--------|------|--------|--------|
| `business_mrr_total` | Gauge | tier | Billing system |
| `business_arr_total` | Gauge | — | Billing system |
| `business_active_tenants` | Gauge | tier | PostgreSQL |
| `business_tenant_churn_rate` | Gauge | — | PostgreSQL |
| `business_gross_margin` | Gauge | tier | cost_inference_total / revenue |
| `business_cogs_per_query` | Gauge | — | cost_inference_total / query_count |

### 22.3 Business Dashboard

```
Executive Summary
├── Daily Active Users           (timeseries, by tier)
├── Queries Per Day              (timeseries, by domain)
├── Query Success Rate           (gauge, 7d rolling)
├── Monthly Recurring Revenue    (timeseries, with forecast)
├── Gross Margin                 (gauge, with target line)
├── Active Tenants               (gauge, by tier)
├── Cost Per Query               (timeseries, by model tier)
└── Top 10 Tenants by Usage      (table)
```

---

## 23. SLO Burn Rate Alerting

### 23.1 Burn Rate Configuration

```yaml
# prometheus-slo-rules.yaml
groups:
  - name: slo-burn-rate
    interval: 1m
    rules:
      # API Uptime SLO: 99.9% over 30d
      - alert: SLO_API_Uptime_FastBurn
        expr: |
          (
            1 - (sum(rate(http_requests_total{status=~"5.."}[2h])) / sum(rate(http_requests_total[2h])))
          ) < 0.999 * 0.95  # 5% error budget consumed in 2h
        for: 2m
        labels:
          severity: critical
          slo: api_uptime
        annotations:
          description: "API uptime SLO fast burn rate exceeded"

      - alert: SLO_API_Uptime_SlowBurn
        expr: |
          (
            1 - (sum(rate(http_requests_total{status=~"5.."}[6h])) / sum(rate(http_requests_total[6h])))
          ) < 0.999 * 0.90  # 10% error budget consumed in 6h
        for: 5m
        labels:
          severity: warning
          slo: api_uptime
        annotations:
          description: "API uptime SLO slow burn rate exceeded"

      # Query Success SLO: 95% over 7d
      - alert: SLO_QuerySuccess_FastBurn
        expr: |
          (
            sum(rate(pipeline_query_count{status="success"}[2h]))
            /
            sum(rate(pipeline_query_count[2h]))
          ) < 0.95 * 0.95
        for: 2m
        labels:
          severity: critical
          slo: query_success
```

### 23.2 Error Budget Calculation

```json
// Grafana annotation showing error budget
{
  "slo": {
    "name": "API Uptime",
    "target": 99.9,
    "window": "30d",
    "total_requests": 2592000,
    "total_error_budget": 2592,  // 0.1% of total
    "consumed_error_budget": 150, // 5.7% consumed
    "remaining_error_budget": 2442,
    "burn_rate": 1.2,  // Consuming faster than budget allows
    "days_until_exhaustion": 18  // At current rate
  }
}
```

---

## 24. Incident Response

### 24.1 Severity Definitions

| Severity | Definition | Examples | Response Time |
|----------|-----------|----------|--------------|
| SEV-1 | Complete platform outage or data loss | All queries failing, DB corrupted, security breach | < 5 min |
| SEV-2 | Significant degradation for many users | High latency, partial query failures, GPU cluster down | < 15 min |
| SEV-3 | Minor degradation or single-tenant issue | One tenant failing, slow but not failing, cosmetic issues | < 1h |
| SEV-4 | Informational | Certificate expiring, storage growing, non-urgent | Next business day |

### 24.2 Incident Response Flow

```
1. DETECTION
   - Automated: Alertmanager → PagerDuty → On-call engineer
   - Manual: User complaint → Slack → On-call engineer
   
2. TRIAGE (5 min)
   - Ack incident in PagerDuty
   - Determine severity (SEV-1 through SEV-4)
   - Create incident channel (#incident-YYYYMMDD-XX)
   - Post initial assessment

3. MITIGATE (15 min for SEV-1)
   - Rollback recent deployment if applicable
   - Scale up resources if capacity issue
   - Fail over if regional outage
   - Block bad traffic if security issue

4. RESOLVE
   - Verify fix in staging
   - Apply fix to production
   - Monitor for 30 min post-fix
   - Close incident channel

5. POST-MORTEM (within 48h for SEV-1/2)
   - Timeline of events
   - Root cause analysis
   - Action items with owners
   - Update runbooks
```

### 24.3 Incident Communication

| Stakeholder | SEV-1 | SEV-2 | SEV-3 |
|-------------|-------|-------|-------|
| On-call engineer | Immediate (PagerDuty) | Immediate (PagerDuty) | Slack |
| Engineering team | #incident channel | #incident channel | #alerts |
| Product/Support | Status page update | Status page update | No notification |
| Customers (Enterprise) | Direct comms within 5 min | Status page | No notification |
| All customers | Status page within 5 min | Status page within 15 min | No notification |

### 24.4 Escalation Path

```
Level 1 (automated):
  Alert → PagerDuty → Primary on-call
  Response time: 5 min

Level 2 (primary on-call → secondary):
  If no response in 5 min: PagerDuty escalates to secondary
  If unresolved in 15 min: Escalate to incident commander

Level 3 (incident commander):
  Assemble response team
  Activate DR plan if needed
  Escalation time: 30 min

Level 4 (executive):
  SEV-1 > 1h: CTO notified
  SEV-1 > 4h: CEO notified
  Customer-visible outage: VP Customer Success notified
```

### 24.5 On-Call Schedule

| Role | Schedule | Coverage |
|------|----------|----------|
| Primary SRE | 1 week rotation | 24/7 |
| Secondary SRE | 1 week rotation (staggered) | 24/7 (backup) |
| Incident Commander | 2 week rotation | Business hours + SEV-1 escalation |
| ML/AI on-call | 1 week rotation (follows sun) | Business hours + pipeline issues |

---

## 25. Observability Testing

### 25.1 Instrumentation Tests

```python
# tests/observability/test_instrumentation.py
def test_metrics_emitted():
    """Every endpoint must emit standard HTTP metrics."""
    response = client.get("/v1/query")
    metrics = get_prometheus_metrics()
    assert metrics["http_requests_total"]["count"] > 0
    assert metrics["http_request_duration_seconds"]["count"] > 0

def test_traces_propagated():
    """Trace context must propagate across service boundaries."""
    # Call public API → should produce trace visible in Tempo
    response = client.get("/v1/query")
    trace_id = response.headers.get("x-trace-id")
    assert trace_id is not None
    # Verify trace appears in Tempo (integration test)
    assert tempo.get_trace(trace_id) is not None

def test_logs_structured():
    """All logs must be valid JSON at INFO and above."""
    log_output = capture_logs(lambda: client.get("/v1/health"))
    for line in log_output:
        json.loads(line)  # Must not raise

def test_otel_span_hierarchy():
    """Query pipeline must produce expected span tree."""
    trace = get_trace_for_query("show revenue by customer")
    assert has_span(trace, "intent_agent")
    assert has_span(trace, "retrieval_agent")
    assert has_span(trace, "planner_agent")
    assert has_span(trace, "generator_agent")
    assert has_span(trace, "policy_enforcement")
```

### 25.2 Prometheus Rule Tests

```python
# tests/observability/test_prometheus_rules.py
def test_prometheus_rules_valid():
    """All Prometheus rules must parse correctly."""
    for rule_file in glob("infra/charts/opencode/**/*.yaml"):
        rules = yaml.safe_load(open(rule_file))
        for group in rules.get("groups", []):
            for rule in group.get("rules", []):
                # Verify expr is valid PromQL
                assert validate_promql(rule["expr"]), f"Invalid PromQL: {rule['expr']}"

def test_recording_rule_slo_computed():
    """SLO recording rules must have correct labels."""
    # Simulate metrics → verify recording rules produce expected output
    pass
```

### 25.3 SLO Validation Tests

```python
# tests/observability/test_slo.py
def test_slo_calculation():
    """SLO burn rate must match expected formula."""
    # Given: 1000 requests, 5 errors in 2h
    # Then: error rate = 0.5%, SLO burn rate = 0.5 (within budget)
    pass

def test_slo_burn_rate_alerting():
    """Burn rate alerts must fire at correct thresholds."""
    # Given: 2% error rate for 2h
    # Then: Fast burn alert must fire
    pass
```

### 25.4 Observability Test Suite

| Test Category | What It Verifies | Frequency | Environment |
|---------------|-----------------|-----------|-------------|
| Instrumentation | Metrics emitted, traces propagated, logs structured | Per PR | CI |
| Prometheus rules | All rules valid PromQL, recording rules produce output | Per PR | CI |
| Grafana dashboards | Dashboards parse, datasources connected | Weekly | Dev |
| SLO calculation | Burn rate matches expected formula | Per release | Staging |
| Alert routing | Alerts reach correct channels | Monthly | Production |
| Trace sampling | Sampling rates within 10% of target | Daily | Production |
| Log retention | Logs present in Loki for expected duration | Weekly | Production |

---

## 26. Operational Playbooks

### 26.1 Playbook: High Error Rate

```yaml
playbook: high_error_rate
trigger: Error rate > 5% for 5 min
severity: SEV-2 (may escalate to SEV-1)

steps:
  - step: 1. ACK
    action: Ack alert in PagerDuty
    expected: Alert acknowledged

  - step: 2. IDENTIFY_SERVICE
    action: Check Grafana Service Overview dashboard
    query: Which service has elevated errors?
    tool: Grafana → Service Overview → Error Rate panel
    expected: Service identified

  - step: 3. CHECK_DEPLOYMENT
    action: Check if recent deployment correlates
    query: Was there a deployment in the last 30 min?
    tool: Grafana annotations or Slack #deployments
    if_recent_deployment: Proceed to rollback (step 5)
    if_no_recent_deployment: Continue to step 4

  - step: 4. INVESTIGATE
    action: Check logs in Loki
    query: '{service="ke-api"} |= "ERROR"'
    tool: Grafana → Explore → Loki
    expected: Error pattern identified

  - step: 5. MITIGATE
    action: |
      if recent_deployment:
        run: ./infra/scripts/rollback.sh production
      elif db_issue:
        run: ./infra/scripts/failover-pg.sh
      elif gpu_issue:
        run: ./infra/scripts/failover-gpu.sh
    expected: Error rate returning to baseline

  - step: 6. VERIFY
    action: Monitor error rate for 15 min
    query: job:error_rate:rate5m
    expected: Error rate < 1%

  - step: 7. DOCUMENT
    action: Create incident report
    template: Post-mortem template
    expected: Incident documented within 48h
```

### 26.2 Playbook: All GPU Nodes Failed

```yaml
playbook: gpu_cluster_down
trigger: All inference pods unhealthy OR GPU node NotReady
severity: SEV-1

steps:
  - step: 1. ACK
    action: Ack alert in PagerDuty
    expected: Alert acknowledged

  - step: 2. VERIFY_FALLBACK
    action: Check model router is using cloud fallback
    query: router_fallback_rate > 0
    tool: Grafana → Model Router dashboard
    expected: Cloud fallback active (GPT-4o)

  - step: 3. NOTIFY
    action: |
      Post to #incident channel:
      "GPU cluster down — all queries routed to GPT-4o (cloud fallback). Cost impact: ~10x normal."
    expected: Team informed

  - step: 4. INVESTIGATE_GPU
    action: Check GPU node health
    commands:
      - kubectl get nodes -l accelerator=amd-gpu
      - kubectl describe nodes gpu-node-1 | grep Conditions
      - kubectl logs -n kube-system -l name=amd-gpu-device-plugin
    expected: Root cause identified (driver issue / hardware failure / OOM)

  - step: 5. MITIGATE
    action: |
      if driver_issue:
        run: ./infra/scripts/bootstrap-gpu-node.sh gpu-node-1
      elif hw_failure:
        run: kubectl taint nodes gpu-node-1 hw-failure=true:NoSchedule
        run: aws autoscaling terminate-instance gpu-node-1
      elif oom:
        run: kubectl cordon gpu-node-1 && kubectl drain gpu-node-1
    expected: GPU nodes recovering

  - step: 6. VERIFY
    action: Check GPU pods becoming healthy
    query: kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=query-pipeline-gpu --timeout=300s
    expected: GPU pods healthy, router switching back from cloud fallback

  - step: 7. POST_MORTEM
    action: |
      - Root cause in #incident channel
      - Track GPU node health trend → proactive replacement
    expected: Incident documented
```

### 26.3 Playbook: Database Corruption

```yaml
playbook: database_corruption
trigger: Multiple policy enforcement violations, validation failures, or user-reported wrong results
severity: SEV-1

steps:
  - step: 1. STOP
    action: |
      # Stop all query processing
      kubectl scale deployment query-pipeline-gpu --replicas=0
      kubectl scale deployment public-api --replicas=1 (maintenance mode)
    expected: No new queries being processed

  - step: 2. ASSESS
    action: Identify scope of corruption
    query: |
      Which tables affected? When did corruption start?
      Check audit logs for last known-good state.
      aws s3 ls s3://opencode-backups/prod/postgresql/daily/
    expected: Scope and timing identified

  - step: 3. RESTORE
    action: |
      # Option A: Point-in-time recovery (preferred)
      aws rds restore-db-instance-to-point-in-time \
        --source-db-instance-identifier opencode-prod \
        --target-db-instance-identifier opencode-prod-restored \
        --restore-time <known-good-timestamp>

      # Option B: Full restore from backup
      aws s3 cp s3://opencode-backups/prod/postgresql/daily/latest.dump /tmp/
      pg_restore --jobs=4 --dbname=$RESTORED_DB_URL /tmp/latest.dump
    expected: Database restored

  - step: 4. VERIFY
    action: Run data integrity checks
    command: python infra/scripts/verify-backup-integrity.py --host $RESTORED_HOST
    expected: All integrity checks pass

  - step: 5. RE-APPLY
    action: Re-apply legitimate data changes from corruption window (if any)
    tool: WAL replay or manual reconciliation
    expected: No data loss

  - step: 6. RESUME
    action: |
      # Point app to restored database
      kubectl set env deployment/ke-api DATABASE_URL=$RESTORED_URL
      kubectl scale deployment query-pipeline-gpu --replicas=3
      kubectl scale deployment public-api --replicas=5
    expected: System operational

  - step: 7. POST_MORTEM
    action: |
      - Root cause analysis within 48h
      - Implement prevention (additional validation, backup frequency)
    expected: Prevention in place
```

### 26.4 Playbook: SLO Burn Rate Exceeded

```yaml
playbook: slo_burn_rate_exceeded
trigger: SLO burn rate > 2 for 2h OR > 1 for 6h
severity: SEV-2 (escalates to SEV-1 if trend continues)

steps:
  - step: 1. IDENTIFY_SLO
    action: Check which SLO is burning
    tool: Grafana → SLO Dashboard
    expected: SLO identified (API uptime, query success, or latency)

  - step: 2. IDENTIFY_CONTRIBUTOR
    action: |
      if api_uptime:
        # Check which endpoint returns errors
        query: sum(rate(http_requests_total{status=~"5.."}[5m])) by (path)
      elif query_success:
        # Check pipeline stage with failures
        query: sum(rate(pipeline_query_count{status="error"}[5m])) by (stage)
      elif latency:
        # Check which service is slow
        query: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) by (service)
    expected: Root cause contributor identified

  - step: 3. INVESTIGATE
    action: Follow service-specific investigation
    tool: Loki logs, Tempo traces, service dashboard
    expected: Root cause found

  - step: 4. REMEDIATE
    action: |
      - Rollback recent deployment (if regression)
      - Add capacity (scale out)
      - Fail over (if regional)
      - Block malicious traffic (if security)
    expected: SLO burn rate returning to normal

  - step: 5. OBSERVE
    action: Monitor SLO for 1h post-remediation
    tool: Grafana → SLO Dashboard → Error Budget panel
    expected: Error budget consumption rate normalizing

  - step: 6. POST_MORTEM
    action: |
      - Document in incident report
      - Add monitoring/alerting if gap found
    expected: Prevention for similar incidents
```

---

## 27. Observability Maturity Model

### 27.1 Current State Assessment

| Domain | Current Level (Phase 1) | Target (Phase 2) | Target (Phase 3) |
|--------|------------------------|-------------------|-------------------|
| Metrics | Standard HTTP + RED | Full RED + component metrics | Auto-instrumentation + custom metrics |
| Logging | Structured JSON stdout | Correlation with traces | Log reduction (log-less alerting) |
| Tracing | Manual OTel instrumentation | Auto-instrumentation (all frameworks) | Adaptive sampling based on SLO health |
| Alerting | Static thresholds | SLO burn rate alerting | Predictive alerting (ML-based) |
| Dashboards | Per-service dashboards | Unified SLO dashboard | Self-healing dashboards |
| SLOs | Platform SLOs defined | Component SLOs + error budgets | Per-tenant SLOs |

### 27.2 Maturity Levels

| Level | Description | Key Indicators |
|-------|-------------|---------------|
| **L1: Basic** | Services emit metrics, logs, traces exist | HTTP RED metrics, structured logs, manual traces |
| **L2: Standard** | Dashboards exist, alerts configured, SLOs defined | Service dashboards, SLO burn rate alerts, runbooks |
| **L3: Advanced** | Auto-instrumentation, custom metrics, tenant-aware | Full OTel auto-instrumentation, per-tenant dashboards |
| **L4: Predictive** | ML-based anomaly detection, predictive alerting | Cost prediction, capacity forecasting, auto-scaling |
| **L5: Autonomous** | Self-healing, auto-remediation | Automated rollback, auto-scaling, auto-remediation |

---

## References

| Source | Relevance |
|--------|-----------|
| [AI-Agent-Specification.md](AI-Agent-Specification.md) §2-9 | Per-agent metrics, observability, and trace configuration |
| [Planner-Specification.md](Planner-Specification.md) §18 | Planner-specific metrics, dashboards, and traces |
| [Retriever-Specification.md](Retriever-Specification.md) §19 | Retriever-specific metrics, quality metrics |
| [KnowledgeEngine-Specification.md](KnowledgeEngine-Specification.md) §14 | KE store operations, extraction, enrichment metrics |
| [Performance-Specification.md](Performance-Specification.md) §13, §15 | KPIs, cost alerting, GPU metrics |
| [API-Specification.md](API-Specification.md) §7 | Metrics Store API for tenant-facing dashboards |
| [Database-Specification.md](Database-Specification.md) §10 | Metrics storage schema, retention |
| [ModelRouter-Specification.md](ModelRouter-Specification.md) §18 | Router and inference model metrics |
| [Infrastructure-Specification.md](Infrastructure-Specification.md) §8-10 | Prometheus, Grafana, Loki, Tempo deployment configuration |
| [Deployment-Specification.md](Deployment-Specification.md) §24 | Monitoring integration, deployment alerts |
| [Engineering-Standards.md](Engineering-Standards.md) §7 | CI/CD test requirements, Definition of Done |
