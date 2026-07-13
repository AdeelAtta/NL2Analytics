# Service Level Agreement (SLA) Definitions

**Project:** SchemaIntern | **Date:** 2026-07-11

---

## 1. Service Level Indicators (SLIs)

| Indicator | Definition | Measurement |
|-----------|-----------|-------------|
| Availability | Percentage of time API responds with 2xx/3xx | `up{job="backend"} == 1` |
| Latency (P95) | 95th percentile of request duration | `histogram_quantile(0.95, ...)` |
| Error Rate | Percentage of 5xx responses | `rate(status=~"5..") / rate(total)` |
| Throughput | Requests per second | `rate(http_requests_total[5m])` |
| Freshness | Age of last successful schema sync | `time() - last_synced_timestamp` |

## 2. Service Level Objectives (SLOs)

### 2.1 API Tier

| Metric | Target | Measurement Window | Severity |
|--------|--------|-------------------|----------|
| Availability | 99.9% | 30 days rolling | Critical |
| P95 Latency — Query | < 5s | 30 days rolling | High |
| P95 Latency — Context | < 500ms | 30 days rolling | Medium |
| P95 Latency — Auth | < 200ms | 30 days rolling | Medium |
| Error Rate | < 1% | 10 minutes | High |

### 2.2 Pipeline Tier

| Stage | P95 Target | Description |
|-------|-----------|-------------|
| Intent Classification | < 100ms | LLM-based, can time out safely |
| Schema Resolution | < 200ms | Database lookup + DDL rendering |
| Planning | < 100ms | Rule-based, deterministic |
| SQL Generation | < 3s | LLM-based with fallback chain |
| Guardrail Enforcement | < 50ms | 10 deterministic layers |
| SQL Execution | < 5s | Dry-run or actual execution |

### 2.3 Sync Tier

| Operation | Target | Frequency |
|-----------|--------|-----------|
| Schema Discovery | < 30s | On demand |
| Full Sync (200 tables) | < 2 min | On demand |
| Incremental Sync | < 30s | Every 5 minutes |

## 3. Service Level Agreements (SLAs)

### 3.1 Free Tier
- Availability: 99.0%
- Max queries: 100/day
- Max connections: 1 database
- Support: Community (GitHub Issues)
- Response time: Best effort

### 3.2 Starter Tier
- Availability: 99.5%
- Max queries: 1,000/day
- Max connections: 3 databases
- Support: Email (4 hour response)
- Response time: 8 business hours

### 3.3 Pro Tier
- Availability: 99.9%
- Max queries: 10,000/day
- Max connections: 10 databases
- Support: Slack (1 hour response)
- Response time: 4 hours

### 3.4 Enterprise Tier
- Availability: 99.95%
- Max queries: Unlimited
- Max connections: Unlimited
- Support: Dedicated Slack channel (15 min response)
- Response time: 1 hour
- SSO/SAML: Included
- Audit logs: 1 year retention

## 4. Monitoring and Alerting

| Alert Rule | Threshold | Duration | Severity | Action |
|-----------|-----------|----------|----------|--------|
| Service Down | `up == 0` | 1 min | Critical | PagerDuty + Slack |
| High Error Rate | `5xx rate > 5%` | 5 min | Critical | PagerDuty + Slack |
| High Latency | `P95 > 5s` | 5 min | Warning | Slack |
| High Memory | `memory > 500MB` | 5 min | Warning | Slack |
| Certificate Expiry | `< 30 days` | — | Warning | Email |

## 5. Credits and Compensation

| Uptime (monthly) | Credit |
|-----------------|--------|
| < 99.9% | 10% credit |
| < 99.5% | 25% credit |
| < 99.0% | 50% credit |
| < 95.0% | 100% credit (full refund) |

## 6. Exclusions

SLAs do not apply to:
- Scheduled maintenance (notified 48 hours in advance)
- Force majeure events
- Customer-side network issues
- Actions taken by customer (misconfiguration, exceeding quotas)
- Third-party service outages (AWS, HuggingFace, OpenAI)
