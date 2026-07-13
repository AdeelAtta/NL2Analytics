# Infrastructure Specification

**Version**: 1.0.0 | **Status**: Approved | **Last Updated**: 2026-07-10

**Cross-References**:
- [Deployment-Specification.md](Deployment-Specification.md) — Deployment modes, config matrix, container resources
- [Security-Specification.md](Security-Specification.md) — Network policies, secret encryption, mTLS
- [Observability-Specification.md](Observability-Specification.md) — Prometheus, Grafana, Loki, OpenTelemetry
- [Cost-Budgets.md](Cost-Budgets.md) — Infrastructure cost per tenant, GPU savings
- [API-Specification.md](API-Specification.md) — Service ports, health endpoints
- [Database-Specification.md](Database-Specification.md) — Storage requirements for PG/Qdrant
- [AI-Agent-Specification.md](AI-Agent-Specification.md) — GPU requirements per model tier

---

## Table of Contents

1. [Cloud Architecture](#1-cloud-architecture)
2. [Docker](#2-docker)
3. [Kubernetes](#3-kubernetes)
4. [Ingress](#4-ingress)
5. [Service Mesh](#5-service-mesh)
6. [Infrastructure-as-Code](#6-infrastructure-as-code)
7. [Secrets Management](#7-secrets-management)
8. [Monitoring](#8-monitoring)
9. [Logging](#9-logging)
10. [Tracing](#10-tracing)
11. [CI/CD](#11-cicd)
12. [Scaling](#12-scaling)
13. [Disaster Recovery](#13-disaster-recovery)
14. [High Availability](#14-high-availability)
15. [Networking](#15-networking)
16. [Storage](#16-storage)
17. [GPU Scheduling](#17-gpu-scheduling)
18. [AMD ROCm](#18-amd-rocm)
19. [Future NVIDIA Compatibility](#19-future-nvidia-compatibility)
20. [On-Prem Support](#20-on-prem-support)
21. [Cost Optimization](#21-cost-optimization)
22. [Deployment Diagrams](#22-deployment-diagrams)

---

## 1. Cloud Architecture

### 1.1 Primary Provider: AWS

All cloud deployments use AWS as primary with cloud-agnostic abstractions via Terraform. Architecture supports migration to GCP or Azure by swapping Terraform modules without changing application code.

### 1.2 Regional Architecture

```
                             AWS Region
+-------------------------------------------------------------------+
|  Availability Zone A       |  Availability Zone B                  |
|  +----------------------+  |  +----------------------+            |
|  | Public Subnet        |  |  | Public Subnet        |            |
|  |   ALB (public)       |  |  |   ALB (public)       |            |
|  +----------------------+  |  +----------------------+            |
|         |                  |         |                             |
|  +----------------------+  |  +----------------------+            |
|  | Private Subnet (app) |  |  | Private Subnet (app) |            |
|  |   ke-api             |  |  |   ke-api             |            |
|  |   public-api         |  |  |   public-api         |            |
|  |   query-pipeline     |  |  |   query-pipeline     |            |
|  |   frontend           |  |  |   frontend           |            |
|  +----------------------+  |  +----------------------+            |
|         |                  |         |                             |
|  +----------------------+  |  +----------------------+            |
|  | Private Subnet (data)|  |  | Private Subnet (data)|            |
|  |   PostgreSQL (RDS)   |  |  |   PostgreSQL (standby)|           |
|  |   Qdrant (primary)   |  |  |   Qdrant (replica)   |            |
|  +----------------------+  |  +----------------------+            |
|         |                  |         |                             |
|  +----------------------+  |  +----------------------+            |
|  | Private Subnet (gpu) |  |  | Private Subnet (gpu) |            |
|  |   Inference pods     |  |  |   Inference pods     |            |
|  |   (AMD MI300X)       |  |  |   (AMD MI300X)       |            |
|  +----------------------+  |  +----------------------+            |
+-------------------------------------------------------------------+
```

### 1.3 Account Structure

| Account | Purpose | Services |
|---------|---------|----------|
| shared-services | Centralized infra | Route53, GuardDuty, ACM, VPC Flow Logs |
| dev | Development | EKS dev, RDS dev, Qdrant dev |
| staging | Pre-production | EKS staging, RDS staging, Qdrant staging |
| prod | Production | EKS prod, RDS prod, Qdrant prod, GPU instances |
| management | CI/CD + monitoring | CodeBuild, Prometheus, Grafana central |

### 1.4 Cloud-Agnostic Layer

All services use env vars and configured endpoints. No AWS-specific SDK calls in app code:

- **Storage**: S3-compatible API (MinIO for on-prem)
- **PostgreSQL**: Standard PG protocol (RDS/CloudSQL/Azure PG)
- **Qdrant**: Self-hosted on K8s (same everywhere)
- **Secrets**: External Secrets Operator (Vault/AWS Secrets/GCP Secret Manager)
- **DNS**: ExternalDNS (Route53/CloudDNS/Azure DNS)
- **Certificates**: cert-manager (Let's Encrypt/ACME)

---

## 2. Docker

### 2.1 Base Images

| Service | Base Image | Tag Policy | Size Target |
|---------|-----------|-----------|-------------|
| ke-api | python:3.12-slim | git-sha-{short} | < 300MB |
| schema-intel | python:3.12-slim | git-sha-{short} | < 400MB |
| query-pipeline (CPU) | python:3.12-slim | git-sha-{short} | < 500MB |
| query-pipeline (GPU) | rocm/pytorch:rocm6.3.2_ubuntu22.04_py3.12_pytorch_release | git-sha-{short} | < 8GB |
| public-api | python:3.12-slim | git-sha-{short} | < 300MB |
| frontend | node:22-alpine (build) -> nginx:alpine (runtime) | git-sha-{short} | < 100MB |
| learning-loop | python:3.12-slim | git-sha-{short} | < 300MB |

### 2.2 Multi-Stage Build Pattern

```
# Dockerfile (all Python services follow this pattern)
FROM python:3.12-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends build-essential
COPY requirements.txt .
RUN pip install --user --no-warn-script-location -r requirements.txt

FROM python:3.12-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 curl
RUN groupadd -g 1001 appuser && useradd -r -u 1001 -g appuser appuser
COPY --from=builder /root/.local /home/appuser/.local
COPY --chown=appuser:appuser src/ /app/
USER appuser
WORKDIR /app
ENV PATH=/home/appuser/.local/bin:$PATH
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:${SERVICE_PORT:-8100}/health || exit 1
ENTRYPOINT ["python", "-m", "app"]
```

### 2.3 GPU Dockerfile (AMD ROCm)

```
# Dockerfile.gpu
FROM rocm/pytorch:rocm6.3.2_ubuntu22.04_py3.12_pytorch_release AS builder
RUN pip install --user vllm==0.6.3 sglang==0.4.1

FROM rocm/pytorch:rocm6.3.2_ubuntu22.04_py3.12_pytorch_release AS runtime
RUN groupadd -g 1001 appuser && useradd -r -u 1001 -g appuser appuser
COPY --from=builder /root/.local /home/appuser/.local
COPY --chown=appuser:appuser src/ /app/
USER appuser
WORKDIR /app
ENV PATH=/home/appuser/.local/bin:$PATH
ENV HIP_VISIBLE_DEVICES=0
ENV HSA_OVERRIDE_GFX_VERSION=11.0.0
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:${INFERENCE_PORT:-8000}/health || exit 1
ENTRYPOINT ["python", "-m", "app.inference.server"]
```

### 2.4 Frontend Dockerfile

```
# Dockerfile.frontend
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

FROM nginx:alpine AS runtime
RUN adduser -D -u 1001 appuser
COPY --from=builder /app/out /usr/share/nginx/html
COPY infra/docker/nginx.conf /etc/nginx/conf.d/default.conf
USER appuser
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://localhost:3000/ || exit 1
```

### 2.5 Image Tagging & Retention

| Tag Format | Source | Retention |
|-----------|--------|-----------|
| {service}:latest | Main branch build | 7 days |
| {service}:git-{sha7} | Every commit | 90 days |
| {service}:v{version} | Release tag | Permanent |
| {service}:pr-{number} | PR build | Deleted on PR close |

### 2.6 Image Registry

- **Primary**: Amazon ECR (production images)
- **Cache**: DockerHub mirror (ghcr.io for open-source)
- **On-prem**: Harbor registry bundled with deployment

---

## 3. Kubernetes

Removed during cleanup — not currently used.

---

## 4. Ingress



### 4.1 Ingress Controller: Traefik

| Attribute | SaaS | Dedicated Cloud | Customer VPC | On-Prem | Air-Gapped |
|-----------|------|----------------|-------------|---------|------------|
| Controller | Traefik | Traefik | Customer choice | Customer choice | nginx |
| TLS | cert-manager + Let's Encrypt | cert-manager | Customer cert | Customer cert | Self-signed |
| External DNS | ExternalDNS (Route53) | ExternalDNS | Customer DNS | Customer DNS | hosts file |

### 4.2 Ingress Routes

```
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: schemaintern-ingress
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: websecure
    cert-manager.io/cluster-issuer: letsencrypt-prod
    traefik.ingress.kubernetes.io/router.middlewares: schemaintern-rate-limit
spec:
  ingressClassName: traefik
  tls:
  - hosts: [app.schemaintern.io]
    secretName: schemaintern-tls
  rules:
  - host: app.schemaintern.io
    http:
      paths:
      - path: /api/v1
        pathType: Prefix
        backend:
          service:
            name: public-api
            port: { number: 8100 }
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend
            port: { number: 3000 }
```

### 4.3 Rate Limiting Middleware

```
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: rate-limit
spec:
  rateLimit:
    average: 100
    burst: 200
    period: 1m
    sourceCriterion:
      requestHeader:
        name: X-Tenant-ID
```

### 4.4 TLS Configuration

| Environment | Certificate Source | Wildcard | Rotation |
|-------------|-------------------|----------|----------|
| Dev | Let's Encrypt (staging) | *.dev.schemaintern.io | Auto |
| Staging | Let's Encrypt (prod) | *.staging.schemaintern.io | Auto |
| Production | Let's Encrypt (prod) | *.schemaintern.io | Auto |
| On-prem | Customer or self-signed | Customer DNS | Manual |
| Air-gapped | Self-signed CA | internal | Manual |

---

## 5. Service Mesh

### 5.1 Selection: Linkerd

| Criteria | Linkerd | Istio | Consul |
|----------|---------|-------|--------|
| Resource overhead | < 10% CPU, < 50MB/proxy | 2-3x more | Moderate |
| mTLS | Automatic | Automatic | Automatic |
| Traffic splitting | SMI-compatible | VirtualService | ServiceResolver |
| Multi-cluster | Yes | Yes (complex) | Yes |
| Operational complexity | Low | High | Medium |
| AMD64 + ARM64 | Yes | Yes | Yes |

**Decision**: Linkerd for simplicity and low overhead. Istio is reserved for Year 2+ when advanced traffic management (canary, A/B, fault injection) is needed.

### 5.2 Linkerd Installation

```
# Install CLI
curl --proto =https --tlsv1.2 -sSfL https://run.linkerd.io/install | sh

# Install control plane
linkerd install --crds | kubectl apply -f -
linkerd install | kubectl apply -f -

# Verify
linkerd check

# Annotate namespace for mesh injection
kubectl annotate ns schemaintern linkerd.io/inject=enabled
```

### 5.3 mTLS Configuration

Linkerd automatically enables mTLS between meshed pods. No additional configuration needed. Traffic between services is encrypted with mTLS using the Linkerd identity controller.

### 5.4 Service Profiles (Retries & Timeouts)

```
apiVersion: linkerd.io/v1alpha2
kind: ServiceProfile
metadata:
  name: ke-api.schemaintern.svc.cluster.local
spec:
  routes:
  - name: GET /health
    condition:
      method: GET
      pathRegex: /health
    isRetryable: false
  - name: POST /v1/store/query
    condition:
      method: POST
      pathRegex: /v1/store/.*
    isRetryable: true
    retries:
      budget:
        minRetriesPerSecond: 10
        retryRatio: 0.2
    timeout: 10s
```

### 5.5 Multi-Cluster Communication

For cross-region failover, Linkerd multi-cluster gateway connects production clusters:

```
linkerd multicluster link --cluster-name us-west-2 | kubectl apply -f -
```

---

## 6. Infrastructure-as-Code

Removed during cleanup — not currently used.

---

## 7. Secrets Management

### 7.1 Architecture

```
[Vault / AWS Secrets Manager]
        |
[External Secrets Operator (K8s)]
        |
[K8s Secrets] (auto-synced, updated on rotation)
        |
[Pods consume via envFrom / volumeMount]
```

### 7.2 Secret Inventory

| Secret | Source | Injected To | Rotation | Length |
|--------|--------|-------------|----------|--------|
| DB credentials | Vault / AWS Secrets | K8s Secret -> env var | 90 days | 32 char |
| JWT signing key | Vault | K8s Secret -> env var | 180 days | 64 char |
| JWT refresh key | Vault | K8s Secret -> env var | 180 days | 64 char |
| Service tokens | Vault | K8s Secret -> env var | 30 days | 43 char (slug) |
| Inference API keys | Vault | K8s Secret -> env var | 180 days | 32 char |
| Qdrant API keys | Vault | K8s Secret -> env var | 90 days | 32 char |
| Encryption keys | Vault (transit) | K8s Secret -> env var | 365 days | 32 bytes |
| TLS certificates | cert-manager | Auto-injected | 90 days | Auto-renewed |
| External DB passwords | Vault | K8s Secret -> env var | 90 days | 32 char |

### 7.3 ExternalSecret Definition

```
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: db-credentials
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: db-credentials
    creationPolicy: Owner
  data:
  - secretKey: database_url
    remoteRef:
      key: schemaintern/prod/database
      property: database_url
  - secretKey: database_password
    remoteRef:
      key: schemaintern/prod/database
      property: password
```

### 7.4 SecretStore Configuration

```
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: vault-backend
spec:
  provider:
    vault:
      server: https://vault.schemaintern.io:8200
      path: schemaintern
      version: v2
      auth:
        kubernetes:
          mountPath: kubernetes
          role: schemaintern-secrets
```

### 7.5 Secrets in CI/CD

Secrets are never stored in CI/CD variables. CI/CD pipelines authenticate to Vault using workload identity (IRSA on EKS, OIDC on GCP):

```
# GitHub Actions OIDC to Vault
- name: Authenticate to Vault
  uses: hashicorp/vault-action@v3
  with:
    url: https://vault.schemaintern.io:8200
    role: ci-role
    method: jwt
    jwtGithubAudience: schemaintern
    secrets: |
      schemaintern/ci/docker-registry username | DOCKER_USERNAME ;
      schemaintern/ci/docker-registry password | DOCKER_PASSWORD
```

---


## 8. Monitoring

### 8.1 Stack: Prometheus + Grafana + Alertmanager

All services expose Prometheus metrics at /metrics (port 9100 sidecar or embedded). kube-prometheus-stack deployed via Helm.

### 8.2 Prometheus Configuration

```
# prometheus-additional.yaml
scrape_configs:
- job_name: schemaintern-services
  kubernetes_sd_configs:
  - role: pod
    selectors:
    - role: pod
      label: app.kubernetes.io/part-of=schemaintern
  relabel_configs:
  - source_labels: [__meta_kubernetes_pod_label_app]
    target_label: service
  - source_labels: [__meta_kubernetes_pod_container_port_number]
    action: drop
    regex: "8200|8100|3000"
```

### 8.3 ServiceMonitor Definition

```
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: schemaintern-servicemonitor
spec:
  selector:
    matchLabels:
      app.kubernetes.io/part-of: schemaintern
  endpoints:
  - port: metrics
    interval: 15s
    path: /metrics
  namespaceSelector:
    matchNames:
    - schemaintern
```

### 8.4 Alertmanager Configuration

```
apiVersion: v1
kind: Secret
metadata:
  name: alertmanager-config
stringData:
  alertmanager.yaml: |
    global:
      slack_api_url: https://hooks.slack.com/services/...
      pagerduty_url: https://events.pagerduty.com/v2/enqueue
    route:
      receiver: default
      routes:
      - match:
          severity: critical
        receiver: pagerduty-critical
        repeat_interval: 5m
      - match:
          severity: warning
        receiver: slack-warning
        repeat_interval: 30m
    receivers:
    - name: pagerduty-critical
      pagerduty_configs:
      - routing_key: <PAGERDUTY_KEY>
        severity: critical
    - name: slack-warning
      slack_configs:
      - channel: "#alerts"
        title: '{{ .GroupLabels.alertname }}'
        text: '{{ .CommonAnnotations.description }}'
```

### 8.5 Grafana Datasources

| Datasource | Type | URL | Access |
|-----------|------|-----|--------|
| Prometheus | prometheus | http://prometheus-operated:9090 | In-cluster |
| Loki | grafana-loki | http://loki:3100 | In-cluster |
| Tempo | tempo | http://tempo:3200 | In-cluster |
| CloudWatch | AWS | custom | IAM role |

### 8.6 Key Dashboards

- **Service Overview**: Request rate, error rate, P50/P95/P99 latency, CPU/memory per service
- **Query Pipeline**: Query volume by status, stage latency, model router decisions, cost accumulation, policy enforcement pass/fail rate
- **Business Metrics**: DAU, queries per user, success rate, avg cost per query, schema sync status
- **Infrastructure**: Cluster health, node resource usage, HPA status, PG/Qdrant metrics, GPU utilization

---

## 9. Logging

### 9.1 Stack: Fluent Bit -> Loki

```
[Pod stdout (JSON)] -> [Fluent Bit (DaemonSet)] -> [Loki] -> [Grafana]
                                                    -> [S3 (cold storage)]
```

### 9.2 Fluent Bit Configuration

```
config:
  service: |
    [SERVICE]
        Flush 1
        Log_Level info
        Parsers_File parsers.conf

  inputs: |
    [INPUT]
        Name tail
        Path /var/log/containers/*.log
        Parser cri
        Tag kube.*

  filters: |
    [FILTER]
        Name kubernetes
        Match kube.*
        Merge_Log On
        K8S-Logging.Parser On

  outputs: |
    [OUTPUT]
        Name loki
        Match kube.*
        Host loki.schemaintern.svc
        Port 3100
        Labels {job="fluentbit"}
        RemoveKeys kubernetes,stream
        AutoKubernetesLabels On
```

### 9.3 Loki Configuration

```
loki:
  config:
    auth_enabled: false
    ingester:
      chunk_target_size: 1536000
      chunk_idle_period: 30m
    limits_config:
      retention_period: 720h  # 30 days
      max_query_lookback: 720h
    schema_config:
      configs:
      - from: 2026-01-01
        store: boltdb-shipper
        object_store: s3
        schema: v12
        index:
          prefix: index_
          period: 24h
    storage_config:
      boltdb_shipper:
        active_index_directory: /data/loki/index
        shared_store: s3
      aws:
        s3: s3://us-east-1/loki-data
        region: us-east-1
        bucketnames: schemaintern-loki-data
```

### 9.4 Log Retention

| Environment | Hot (Loki) | Cold (S3) | Queryable |
|-------------|-----------|----------|-----------|
| Dev | 1 day | None | Grafana |
| Staging | 7 days | 30 days | Grafana + S3 |
| Production | 30 days | 90 days | Grafana + S3 |
| Audit (prod) | 90 days | 365 days | S3 only (Athena) |

---

## 10. Tracing

### 10.1 Stack: OpenTelemetry Collector -> Tempo

```
[App (OTel SDK)] -> [OTel Collector (sidecar)] -> [Tempo] -> [Grafana]
                                                  -> [S3 (storage)]
```

### 10.2 OTel Collector Configuration

```
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
    send_batch_size: 200
  memory_limiter:
    check_interval: 1s
    limit_mib: 500
  attributes:
    actions:
    - key: environment
      value: prod
      action: upsert

exporters:
  otlp/tempo:
    endpoint: tempo.schemaintern.svc:4317
    tls:
      insecure: true

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch, attributes]
      exporters: [otlp/tempo]
```

### 10.3 Tempo Configuration

```
tempo:
  storage:
    trace:
      backend: s3
      s3:
        bucket: schemaintern-tempo-traces
        endpoint: s3.us-east-1.amazonaws.com
        region: us-east-1
  ingester:
    max_block_duration: 30m
  compactor:
    compaction:
      block_retention: 48h
  querier:
    max_find_traces: 1000
  metrics_generator:
    processor:
      service_graphs:
        dimensions: [environment]
      span_metrics:
        dimensions: [service, method]
```

### 10.4 Trace Sampling

| Environment | Sampling Rate | Strategy |
|-------------|--------------|----------|
| Dev | 100% | All traces |
| Staging | 10% | Head-based |
| Production | 1% | Head-based, 100% for errors |
| Production (errors) | 100% | Tail-based |

### 10.5 OTel SDK Integration (Python)

```
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

provider = TracerProvider()
processor = BatchSpanProcessor(
    OTLPSpanExporter(endpoint="http://localhost:4317")
)
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
```

---

## 11. CI/CD

### 11.1 Pipeline Architecture

```
[Git Push] -> [GitHub Actions] -> [Build + Test] -> [Push Image to ECR]
                              -> [Deploy to Dev]  -> [Integration Tests]
                              -> [Promote to Staging] -> [E2E Tests]
                              -> [Promote to Prod] -> [Canary -> Rollout]
```

### 11.2 GitHub Actions Workflow

```yaml
name: Build and Deploy
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  REGISTRY: ${{ secrets.ECR_REGISTRY }}
  K8S_NAMESPACE: schemaintern

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: { python-version: '3.12' }
    - run: pip install -r requirements.txt
    - run: pytest tests/unit/
    - run: ruff check src/
    - run: mypy src/

  build:
    needs: [test]
    runs-on: ubuntu-latest
    strategy:
      matrix:
        service: [ke-api, public-api, query-pipeline, frontend]
    steps:
    - uses: actions/checkout@v4
    - uses: aws-actions/configure-aws-credentials@v4
      with:
        role-to-assume: arn:aws:iam::xxx:role/github-actions-ecr
        aws-region: us-east-1
    - id: login-ecr
      uses: aws-actions/amazon-ecr-login@v2
    - run: |
        docker build \
          -t $REGISTRY/${{ matrix.service }}:${{ github.sha }} \
          -f infra/docker/Dockerfile.${{ matrix.service }} .
        docker push $REGISTRY/${{ matrix.service }}:${{ github.sha }}

  deploy-dev:
    needs: [build]
    runs-on: ubuntu-latest
    environment: dev
    steps:
    - uses: aws-actions/configure-aws-credentials@v4
      with:
        role-to-assume: arn:aws:iam::xxx:role/github-actions-eks
        aws-region: us-east-1
    - run: aws eks update-kubeconfig --name schemaintern-dev --region us-east-1
    - run: |
        helm upgrade --install schemaintern infra/charts/schemaintern \
          --namespace $K8S_NAMESPACE \
          -f infra/charts/schemaintern/values/dev.yaml \
          --set images.tag=${{ github.sha }} \
          --wait --timeout 5m

  deploy-staging:
    needs: [deploy-dev]
    runs-on: ubuntu-latest
    environment: staging
    steps:
    - uses: aws-actions/configure-aws-credentials@v4
      with:
        role-to-assume: arn:aws:iam::xxx:role/github-actions-eks
        aws-region: us-east-1
    - run: aws eks update-kubeconfig --name schemaintern-staging --region us-east-1
    - run: |
        helm upgrade --install schemaintern infra/charts/schemaintern \
          --namespace $K8S_NAMESPACE \
          -f infra/charts/schemaintern/values/staging.yaml \
          --set images.tag=${{ github.sha }} \
          --wait --timeout 5m

  deploy-prod:
    needs: [deploy-staging]
    runs-on: ubuntu-latest
    environment: production
    steps:
    - uses: aws-actions/configure-aws-credentials@v4
      with:
        role-to-assume: arn:aws:iam::xxx:role/github-actions-eks
        aws-region: us-east-1
    - run: aws eks update-kubeconfig --name schemaintern-prod --region us-east-1
    - run: |
        helm upgrade --install schemaintern infra/charts/schemaintern \
          --namespace $K8S_NAMESPACE \
          -f infra/charts/schemaintern/values/prod.yaml \
          --set images.tag=${{ github.sha }} \
          --wait --timeout 10m
```

### 11.3 Promotion Gates

| Environment | Approval Required | Tests Required | Rollback Strategy |
|-------------|-----------------|---------------|-------------------|
| Dev | None | Unit + lint | helm rollback |
| Staging | PR review | Integration + E2E | helm rollback |
| Production | 2 approvals + QA sign-off | Full suite + canary | helm rollback + git revert |

### 11.4 ArgoCD (GitOps)

For production, ArgoCD manages the desired state:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: schemaintern-prod
spec:
  destination:
    namespace: schemaintern
    server: https://kubernetes.default.svc
  project: default
  source:
    repoURL: https://github.com/schemaintern/infra
    path: infra/charts/schemaintern
    targetRevision: main
    helm:
      valueFiles:
      - values/prod.yaml
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
```

### 11.5 Image Build Matrix

| Service | Build Trigger | Build Time Target | Image Size Target |
|---------|-------------|-------------------|-------------------|
| ke-api | PR + main | 3 min | 200MB |
| public-api | PR + main | 3 min | 200MB |
| query-pipeline | PR + main | 5 min | 400MB |
| query-pipeline-gpu | main only | 15 min | 6GB |
| frontend | PR + main | 4 min | 80MB |
| schema-intel | PR + main | 3 min | 300MB |
| learning-loop | PR + main | 3 min | 200MB |

---


## 12. Scaling

### 12.1 Horizontal Pod Autoscaler (HPA)

| Service | Metric | Target | Min Replicas | Max Replicas |
|---------|--------|--------|-------------|-------------|
| ke-api | CPU | 70% | 2 | 10 |
| public-api | CPU + memory | 70% | 2 | 20 |
| frontend | CPU | 70% | 2 | 10 |
| query-pipeline (CPU) | CPU | 60% | 2 | 20 |
| query-pipeline (GPU) | custom (queue depth) | 5 pending | 2 | 10 |
| schema-intel | CPU | 70% | 1 | 5 |
| learning-loop | CPU | 70% | 1 | 2 |

```
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ke-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ke-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 25
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 60
      - type: Pods
        value: 4
        periodSeconds: 60
```

### 12.2 Cluster Autoscaler

```
apiVersion: v1
kind: ConfigMap
metadata:
  name: cluster-autoscaler-config
data:
  config: |
    nodeGroups:
    - name: system
      minSize: 2
      maxSize: 5
    - name: ke-store
      minSize: 2
      maxSize: 5
    - name: pipeline-cpu
      minSize: 2
      maxSize: 10
    - name: pipeline-gpu
      minSize: 2
      maxSize: 10
    scaleDownUtilizationThreshold: 0.5
    scaleDownUnneededTime: 10m
    maxNodeProvisionTime: 15m
```

### 12.3 Vertical Pod Autoscaler (VPA)

For batch workloads (schema-intel, learning-loop) to right-size resource requests:

```
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: schema-intel-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: schema-intel
  updatePolicy:
    updateMode: Auto
  resourcePolicy:
    containerPolicies:
    - containerName: '*'
      minAllowed:
        cpu: 500m
        memory: 512Mi
      maxAllowed:
        cpu: 4
        memory: 8Gi
```

### 12.4 Database Scaling

| Stage | Tenants | PostgreSQL | Qdrant | Strategy |
|-------|---------|-----------|--------|----------|
| 1 | < 100 | db.r6g.large (shared) | 3-node cluster | Baseline |
| 2 | 100-500 | db.r6g.xlarge + read replicas | 5-node cluster + replicas | Vertical |
| 3 | 500-1K | db.r6g.2xlarge + pgpool | 7-node cluster + sharding | Vertical + read replicas |
| 4 | 1K-5K | db.r6g.4xlarge, per-tenant DBs | Per-tenant collections | Horizontal (DB-per-tenant) |
| 5 | 5K-10K | Aurora + Global Database | Multi-region Qdrant | Global scale |

### 12.5 GPU Scaling

GPU pods scale on custom metrics (inference queue depth). Each GPU node hosts up to 8 inference pods (MI300X has 192GB, model sizes 7B-70B):

| Model | GPU Memory | Pods per MI300X | Batch Size |
|-------|-----------|----------------|-----------|
| SQLCoder-7b | 16GB | 8 | 4 |
| Qwen2.5-72B (INT4) | 48GB | 3 | 2 |
| DeepSeek-V3 (INT4) | 72GB | 2 | 1 |
| GPT-4o (API fallback) | N/A | N/A | N/A |

---

## 13. Disaster Recovery

### 13.1 RPO/RTO Targets

| Tier | RPO | RTO | Notes |
|------|-----|-----|-------|
| Free/Starter | 24h | 4h | Daily backups, warm standby |
| Pro | 4h | 1h | Continuous WAL archiving, multi-AZ |
| Enterprise | 5min | 15min | Cross-region active-active (Year 2) |

### 13.2 Backup Strategy

| Data | Method | Frequency | Retention | Location |
|------|--------|-----------|-----------|----------|
| PostgreSQL | pg_dump + WAL archiving | Continuous (WAL) + daily (full) | 30 days (daily), 7 days (WAL) | S3 (same region) |
| PostgreSQL (Enterprise) | pg_dump + WAL streaming | Continuous | 7 days (WAL), 90 days (daily) | S3 (cross-region) |
| Qdrant | Snapshot API | Daily | 7 days | S3 (same region) |
| KE embeddings | Periodic export | Daily | 30 days | S3 |
| Config | Git (IaC) | Per change | Permanent | GitHub |
| Audit logs | S3 export | Hourly | 365 days | S3 (Glacier after 90d) |
| Prometheus | Thanos sidecar | 2h blocks | 180 days | S3 |

### 13.3 PostgreSQL Backup Automation

```
# infra/scripts/backup-pg.sh
#!/bin/bash
set -euo pipefail

BACKUP_BUCKET="s3://schemaintern-backups/${ENVIRONMENT}/postgresql"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# Full backup
PGPASSWORD=$DB_PASSWORD pg_dump \
  -h $DB_HOST \
  -U $DB_USER \
  -d $DB_NAME \
  --format=custom \
  --compress=9 \
  --file=/tmp/backup-${TIMESTAMP}.dump

# Upload to S3
aws s3 cp /tmp/backup-${TIMESTAMP}.dump ${BACKUP_BUCKET}/daily/

# Cleanup local
rm /tmp/backup-${TIMESTAMP}.dump

# Retention: delete backups older than 30 days
aws s3 ls ${BACKUP_BUCKET}/daily/ | while read -r line; do
  create_date=$(echo $line | awk '{print $1}')
  if [[ $(date -d "$create_date" +%s) -lt $(date -d '30 days ago' +%s) ]]; then
    filename=$(echo $line | awk '{print $4}')
    aws s3 rm ${BACKUP_BUCKET}/daily/${filename}
  fi
done
```

### 13.4 Restore Procedure

```
1. Identify backup: aws s3 ls s3://schemaintern-backups/prod/postgresql/daily/
2. Download backup: aws s3 cp s3://.../backup-20260710-120000.dump /tmp/
3. Restore: pg_restore -h $TARGET_HOST -U $TARGET_USER -d $TARGET_DB \
     --jobs=4 --verbose /tmp/backup-20260710-120000.dump
4. Verify: Run health check queries against restored database
5. Fail over: Update K8s ConfigMap to point to restored DB
6. Rollback: If restore fails, point back to original DB
```

### 13.5 Cross-Region DR (Enterprise)

| Component | Primary (us-east-1) | DR (us-west-2) | Cutover |
|-----------|-------------------|----------------|---------|
| PostgreSQL | RDS Multi-AZ | RDS Cross-region replica | Promote replica |
| Qdrant | Primary cluster | Read-only replica | Promote replica, re-point |
| App | EKS primary | EKS DR (warm) | Scale up DR, Route53 failover |
| DNS | Route53 primary | Route53 health check | Automatic (Route53 failover) |
| Static assets | S3 + CloudFront | S3 cross-region replication | Automatic |

### 13.6 DR Testing Schedule

| Test | Frequency | Scope | Success Criteria |
|-----|-----------|-------|-----------------|
| Backup integrity | Daily | Automated restore test on staging | All tables present, row counts match |
| Restore drill | Quarterly | Full restore to DR environment | RTO met, all services operational |
| Failover test | Bi-annual | Actual failover to DR region | Zero data loss, RTO met |
| Chaos engineering | Bi-annual | Inject failures (network, DB, GPU) | System degrades gracefully |

---

## 14. High Availability

### 14.1 Multi-AZ Architecture

All production infrastructure spans at least 2 availability zones within a region. Each AZ has complete compute, storage, and networking capacity.

### 14.2 Service HA Design

| Component | HA Mechanism | Failure Mode | Recovery |
|-----------|-------------|-------------|----------|
| ke-api | 3+ replicas, pod anti-affinity, PDB | Single pod failure | K8s reschedules |
| public-api | 3+ replicas, spread across AZs | AZ failure | ALB routes to other AZ |
| frontend | 2+ replicas, stateless | Pod failure | Immediate replacement |
| query-pipeline | 2+ replicas, GPU anti-affinity | GPU node failure | Reschedule on healthy GPU node |
| PostgreSQL | Multi-AZ RDS (sync standby) | AZ failure | Automatic failover (< 60s) |
| Qdrant | 3-node cluster (N=3, R=2, W=2) | Node failure | Automatic re-replication |
| Redis (cache) | 2-node cluster (sentinel) | Node failure | Sentinel promotes replica |

### 14.3 Graceful Shutdown

```
# PreStop hook (all services)
lifecycle:
  preStop:
    exec:
      command:
      - sh
      - -c
      - |
        # Drain in-flight requests
        sleep 5
        # Signal health check failure
        touch /tmp/stopping
        # Wait for LB to drain connections
        sleep $(POD_GRACE_PERIOD)
```

### 14.4 Pod Anti-Affinity Rules

| Service | Rule Type | Topology Key | Rationale |
|---------|-----------|-------------|-----------|
| ke-api | preferred | zone | Spread across AZs |
| public-api | preferred | zone | Spread across AZs |
| query-pipeline-gpu | required | hostname | Max 1 GPU pod per node |
| postgres | required | zone | Separate AZs for primary/standby |

### 14.5 Readiness Gates

```
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      readinessGates:
      - conditionType: "linkerd.io/ready"
```

---

## 15. Networking

### 15.1 VPC Design

| Environment | CIDR | Public Subnets | Private Subnets | NAT Gateway |
|-------------|------|---------------|----------------|------------|
| Dev | 10.0.0.0/16 | 2 (/24 each) | 6 (/20 each) | Single |
| Staging | 10.1.0.0/16 | 2 (/24 each) | 6 (/20 each) | Single |
| Production | 10.2.0.0/16 | 2 (/24 each) | 6 (/20 each) | Multi-AZ |
| Production DR | 10.3.0.0/16 | 2 (/24 each) | 6 (/20 each) | Multi-AZ |

### 15.2 Subnet Layout

```
10.2.0.0/16 (Production VPC)
+-- 10.2.0.0/20    Public ALB subnets (AZ-A, AZ-B)
|   +-- 10.2.0.0/24  us-east-1a public
|   +-- 10.2.1.0/24  us-east-1b public
+-- 10.2.16.0/20   Application subnets
|   +-- 10.2.16.0/24 us-east-1a app
|   +-- 10.2.17.0/24 us-east-1b app
+-- 10.2.32.0/20   Data store subnets
|   +-- 10.2.32.0/24 us-east-1a data
|   +-- 10.2.33.0/24 us-east-1b data
+-- 10.2.48.0/20   GPU subnets
|   +-- 10.2.48.0/24 us-east-1a gpu
|   +-- 10.2.49.0/24 us-east-1b gpu
+-- 10.2.64.0/20   Internal LB subnets
    +-- 10.2.64.0/24 us-east-1a internal
    +-- 10.2.65.0/24 us-east-1b internal
```

### 15.3 Security Groups

| Security Group | Rule | Source/Destination | Purpose |
|---------------|------|-------------------|---------|
| alb-sg | Inbound: 443 (HTTPS) | 0.0.0.0/0 | Public traffic |
| alb-sg | Outbound: 8100, 3000 | app-sg | Forward to services |
| app-sg | Inbound: 8100, 8200, 3000 | alb-sg, internal-lb-sg | App traffic |
| app-sg | Inbound: 4317 (OTel) | monitoring-sg | Trace collection |
| data-sg | Inbound: 5432 (PG) | app-sg | Database access |
| data-sg | Inbound: 6333 (Qdrant) | app-sg | Vector DB access |
| gpu-sg | Inbound: 8000 (inference) | app-sg | Model serving |
| monitoring-sg | Inbound: 9090 (Prom) | alb-sg (internal) | Metrics access |

### 15.4 K8s Network Policies

```
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-api-to-ke
spec:
  podSelector:
    matchLabels:
      app: ke-api
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: public-api
    ports:
    - protocol: TCP
      port: 8200
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-app-to-db
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: postgres
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app.kubernetes.io/part-of: schemaintern
    ports:
    - protocol: TCP
      port: 5432
```

### 15.5 Service Mesh mTLS

With Linkerd injected, all inter-service traffic is automatically encrypted with mTLS. No additional network policy is needed for encryption. Network policies control which pods can communicate; Linkerd handles encryption.

---

## 16. Storage

### 16.1 Storage Classes

| Name | Provisioner | Reclaim Policy | Volume Binding | IOPS | Use Case |
|------|------------|---------------|---------------|------|----------|
| gp3 | ebs.csi.aws.com | Delete | WaitForFirstConsumer | 3000 base | General purpose |
| io2 | ebs.csi.aws.com | Retain | WaitForFirstConsumer | 16000 | PostgreSQL |
| local-ssd | node-local | Delete | Immediate | N/A | Qdrant (fast) |
| efs | efs.csi.aws.com | Delete | Immediate | N/A | Shared storage |

### 16.2 Persistent Volume Claims

```
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-data
spec:
  accessModes:
  - ReadWriteOnce
  storageClassName: io2
  resources:
    requests:
      storage: 500Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: qdrant-data
spec:
  accessModes:
  - ReadWriteOnce
  storageClassName: local-ssd
  resources:
    requests:
      storage: 200Gi
```

### 16.3 Storage Requirements by Service

| Service | Storage Type | Size | IOPS | Growth Rate | Backup Method |
|---------|-------------|------|------|-------------|--------------|
| PostgreSQL (shared) | io2 (EBS) | 500Gi | 16000 | 10Gi/month | pg_dump + WAL |
| PostgreSQL (per-tenant) | io2 (EBS) | 100Gi | 3000 | 1Gi/month | pg_dump + WAL |
| Qdrant (shared) | local-ssd | 200Gi | N/A | 5Gi/month | Snapshot |
| Qdrant (per-tenant) | local-ssd | 50Gi | N/A | 500Mi/month | Snapshot |
| Redis | gp3 | 20Gi | 3000 | Static | RDB snapshots |
| Prometheus | gp3 | 100Gi | 3000 | 2Gi/month | Thanos S3 |
| Loki | gp3 | 200Gi | 3000 | 5Gi/month | S3 |

### 16.4 Volume Snapshot & Restore

```
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshotClass
metadata:
  name: ebs-snapshot
driver: ebs.csi.aws.com
deletionPolicy: Delete
---
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: postgres-snapshot-20260710
spec:
  volumeSnapshotClassName: ebs-snapshot
  source:
    persistentVolumeClaimName: postgres-data
```

---

## 17. GPU Scheduling

### 17.1 AMD GPU Device Plugin

```
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: amd-gpu-device-plugin
spec:
  selector:
    matchLabels:
      name: amd-gpu-device-plugin
  template:
    spec:
      nodeSelector:
        accelerator: amd-gpu
      tolerations:
      - key: dedicated
        operator: Equal
        value: gpu
        effect: NoSchedule
      containers:
      - name: device-plugin
        image: rocm/k8s-device-plugin:latest
        securityContext:
          privileged: true
        volumeMounts:
        - name: device-plugin
          mountPath: /var/lib/kubelet/device-plugins
        - name: sys
          mountPath: /sys
      volumes:
      - name: device-plugin
        hostPath:
          path: /var/lib/kubelet/device-plugins
      - name: sys
        hostPath:
          path: /sys
```

### 17.2 Node Labeling

```
# Label GPU nodes
kubectl label node gpu-node-1 accelerator=amd-gpu
kubectl label node gpu-node-1 pool=pipeline-gpu

# Taint GPU nodes (prevent non-GPU pods)
kubectl taint nodes gpu-node-1 dedicated=gpu:NoSchedule
```

### 17.3 GPU Resource Requests

Pods request GPUs via extended resource:

```
resources:
  requests:
    amd.com/gpu: 1
  limits:
    amd.com/gpu: 1
```

### 17.4 GPU Pod Scheduling Strategy

| Workload | GPU Count | Scheduling Strategy | Co-location |
|----------|-----------|--------------------|-------------|
| SQLCoder-7b (batch) | 1 per 8 pods | Spread across nodes | Yes, share GPU |
| Qwen2.5-72B (interactive) | 1 per 3 pods | Dedicated node preferred | Limited (3 per GPU) |
| DeepSeek-V3 (complex) | 1 per 2 pods | Dedicated node | Limited (2 per GPU) |
| Embedding (BGE-M3) | 1 per 16 pods | Spread across nodes | Yes, share GPU |

### 17.5 GPU Monitoring

```
# Node-level GPU metrics
kubectl exec -n kube-system amd-gpu-device-plugin-xxxx -- rocm-smi

# Prometheus GPU metrics (via AMDC exporter)
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: amd-gpu-exporter
spec:
  endpoints:
  - port: metrics
    interval: 15s
  selector:
    matchLabels:
      app.kubernetes.io/name: amd-gpu-exporter
```

---


## 18. AMD ROCm

### 18.1 ROCm Stack Version

| Component | Version | Notes |
|-----------|---------|-------|
| ROCm | 6.3.2 | Stable release, vLLM/SGLang support |
| HIP | 6.3.2 | CUDA-compatible API layer |
| ROCclr | 6.3.2 | Runtime language |
| MIOpen | 3.2.0 | ML primitives (GEMM, convolutions) |
| RCCL | 2.20.0 | Multi-GPU communication |
| ROCm Validation Suite | 6.3.2 | Health checks |

### 18.2 GPU Node Bootstrap

```
# infra/scripts/bootstrap-gpu-node.sh
#!/bin/bash
set -euo pipefail

# Install ROCm drivers
wget https://repo.radeon.com/amdgpu-install/6.3.2/ubuntu/jammy/amdgpu-install_6.3.2-1_all.deb
dpkg -i amdgpu-install_6.3.2-1_all.deb
apt-get update
amdgpu-install -y --usecase=rocm

# Verify installation
rocm-smi --showhw
rocminfo | grep "Name:"
hipconfig --full

# Set GPU compute mode to EXCLUSIVE_PROCESS
rocm-smi --setcomputemode 0 -c EXCLUSIVE_PROCESS

# Enable MIG-like partitioning (if applicable)
# For MI300X: 8 GCDs, no MIG needed

# Label node for scheduling
kubectl label node $(hostname) accelerator=amd-gpu pool=pipeline-gpu
kubectl taint nodes $(hostname) dedicated=gpu:NoSchedule
```

### 18.3 ROCm Environment Variables

```
# Pod env vars for ROCm
env:
- name: HIP_VISIBLE_DEVICES
  value: "0"              # Map GPU 0 to container
- name: HSA_OVERRIDE_GFX_VERSION
  value: "11.0.0"         # MI300X GFX version
- name: ROCR_VISIBLE_DEVICES
  value: "0"              # ROCm runtime visible devices
- name: GPU_MAX_HW_QUEUES
  value: "16"             # Max HW queues for vLLM
- name: HIP_FORCE_DEV_KERNARG
  value: "1"              # Force device kernel args
```

### 18.4 vLLM + ROCm Configuration

```
# vLLM ROCm server startup
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-72B-Instruct \
  --dtype half \
  --max-model-len 16384 \
  --gpu-memory-utilization 0.90 \
  --tensor-parallel-size 2 \
  --pipeline-parallel-size 1 \
  --trust-remote-code \
  --host 0.0.0.0 \
  --port 8000

# Environment for ROCm + vLLM
export PYTORCH_HIP_ALLOC_CONF=garbage_collection_threshold:0.8
export VLLM_AMD_KERNEL_FLAGS=1
```

### 18.5 ROCm Validation Suite

```
# Run RVS health check
rvs -a --config conf/rock.yaml

# GPU memory test
rocm-bandwidth-test

# Matrix multiplication test
rocblas-bench --function gemm --size 4096x4096x4096

# Multi-GPU test
rccl-tests all_reduce_perf -b 128M -e 1G -f 2 -g 8
```

### 18.6 Known Limitations & Mitigations

| Limitation | Impact | Mitigation |
|-----------|--------|-----------|
| Larger Docker image size (8GB vs 6GB NVIDIA) | Slower pull times | ECR pull-through cache, image streaming |
| Flash Attention 2 not available | ~15% slower inference | Use sdp backend, plan FA2 port |
| vLLM ROCm prefill speed ~10% slower | Higher P99 latency | Over-provision GPU nodes by 15% |
| Fewer community models tested | Compatibility risk | Run model validation in CI, pin tested versions |
| No CUDA Graphs on ROCm | Higher per-request overhead | Use continuous batching in vLLM |

---

## 19. Future NVIDIA Compatibility

### 19.1 Abstraction Layer

The inference layer abstracts GPU vendor via environment variables and conditional code paths:

```
# lib/inference/backends.py
import os
from enum import Enum

class GPUPlatform(Enum):
    AMD_ROCM = "rocm"
    NVIDIA_CUDA = "cuda"

def detect_gpu_platform() -> GPUPlatform:
    if os.path.exists("/proc/driver/nvidia"):
        return GPUPlatform.NVIDIA_CUDA
    if os.path.exists("/opt/rocm"):
        return GPUPlatform.AMD_ROCM
    return GPUPlatform.AMD_ROCM  # Default to ROCm

def get_vllm_kwargs():
    platform = detect_gpu_platform()
    if platform == GPUPlatform.NVIDIA_CUDA:
        return {
            "dtype": "half",
            "tensor_parallel_size": int(os.getenv("GPU_COUNT", "1")),
            "enable_flash_attention": True,
        }
    else:
        return {
            "dtype": "half",
            "tensor_parallel_size": int(os.getenv("GPU_COUNT", "1")),
            "enable_flash_attention": False,  # Not available on ROCm
        }
```

### 19.2 Conditional Scheduling

```
# Helm values.yaml
gpu:
  platform: amd  # or: nvidia
  devicePlugin:
    amd:
      image: rocm/k8s-device-plugin:latest
    nvidia:
      image: nvidia/k8s-device-plugin:v0.17.0

# templates/_gpu.tpl
{{- if eq .Values.gpu.platform "amd" }}
resources:
  requests:
    amd.com/gpu: 1
  limits:
    amd.com/gpu: 1
{{- else if eq .Values.gpu.platform "nvidia" }}
resources:
  requests:
    nvidia.com/gpu: 1
  limits:
    nvidia.com/gpu: 1
{{- end }}
```

### 19.3 NVIDIA GPU Node Pool

| Attribute | Value |
|-----------|-------|
| Instance type | g6e.12xlarge (4x NVIDIA L4) or p4d.24xlarge (8x A100) |
| Min/Max | 2/10 |
| Device plugin | nvidia/k8s-device-plugin:v0.17.0 |
| Runtime | nvidia-container-toolkit |
| CUDA version | 12.4+ |

### 19.4 Migration Path

```
Phase 1 (now):    AMD ROCm only (MI300X)
Phase 2 (Y2 Q1):  Add NVIDIA support, dual-registry for GPU images
Phase 3 (Y2 Q3):  Auto-detect GPU platform at startup
Phase 4 (Y3):     Vendor-agnostic GPU pool (mix AMD + NVIDIA)
```

---

## 20. On-Prem Support

### 20.1 Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Kubernetes | 1.28+ | 1.31+ |
| CPU (total) | 32 cores | 64+ cores |
| RAM (total) | 128GB | 256GB+ |
| GPU | AMD MI100+ | AMD MI300X |
| GPU memory | 32GB | 128GB+ |
| Storage (SSD) | 500GB | 2TB+ |
| Nodes | 3 | 5+ |
| Network | 10Gbps | 25Gbps+ |
| PostgreSQL | 14+ | 16 |

### 20.2 Air-Gapped Deployment

No external network access. All containers and dependencies must be bundled:

```
# Bundle structure
schemaintern-airgapped-v1.0.0/
+-- images/                    # All container images (docker save)
|   +-- schemaintern-services.tar.gz
|   +-- postgres.tar.gz
|   +-- qdrant.tar.gz
|   +-- prometheus.tar.gz
|   +-- loki.tar.gz
|   +-- linkerd.tar.gz
|   +-- traefik.tar.gz
|   +-- cert-manager.tar.gz
+-- charts/                    # All Helm charts with dependencies vendored
|   +-- schemaintern/
|   +-- dependencies/
+-- scripts/
|   +-- load-images.sh
|   +-- install.sh
|   +-- configure.sh
+-- config/
|   +-- values-air-gapped.yaml
|   +-- self-signed-ca/
+-- docs/
    +-- INSTALL.md
    +-- CONFIGURE.md
    +-- OPERATE.md
```

### 20.3 On-Prem Installation Script

```
# scripts/install.sh
#!/bin/bash
set -euo pipefail

echo "=== SchemaIntern Air-Gapped Installation ==="

# 1. Load container images
echo "Loading container images..."
for bundle in images/*.tar.gz; do
  gunzip -c "$bundle" | docker load
done

# 2. Install Helm charts
echo "Installing infrastructure..."
helm install linkerd charts/dependencies/linkerd --namespace linkerd --create-namespace
helm install traefik charts/dependencies/traefik --namespace traefik --create-namespace
helm install cert-manager charts/dependencies/cert-manager --namespace cert-manager --create-namespace
helm install prometheus charts/dependencies/prometheus --namespace monitoring --create-namespace
helm install loki charts/dependencies/loki --namespace monitoring

# 3. Deploy application
echo "Deploying SchemaIntern..."
helm install schemaintern charts/schemaintern \
  --namespace schemaintern --create-namespace \
  -f config/values-air-gapped.yaml

# 4. Configure self-signed CA
echo "Configuring TLS..."
kubectl apply -f config/self-signed-ca/

# 5. Verify deployment
echo "Verifying deployment..."
kubectl wait --for=condition=ready pod -l app.kubernetes.io/part-of=schemaintern \
  --namespace schemaintern --timeout=300s

echo "=== Installation Complete ==="
echo "Access the application at: https://schemaintern.internal:443"
```

### 20.4 Offline Helm Dependencies

```
# Vendor Helm dependencies for air-gapped deployment
helm dependency build infra/charts/schemaintern/
# Vendors all dependencies into charts/ subdirectory
# No network access needed during install
```

### 20.5 Upgrades for On-Prem

Pull-based update model: Customer retrieves release bundle, runs upgrade script.

```
# scripts/upgrade.sh v1.0.0 -> v1.1.0
./scripts/upgrade.sh --bundle schemaintern-airgapped-v1.1.0.tar.gz
```

---

## 21. Cost Optimization

### 21.1 Compute Optimization

| Strategy | Savings | Risk | Implementation |
|----------|---------|------|---------------|
| Spot instances (dev/staging) | 60-70% | Interruption risk | Dev + staging only; PDB for graceful handling |
| Spot instances (prod CPU) | 50-60% | Node termination | Labels + tolerations for non-critical workloads |
| Reserved instances (prod base) | 30-40% | 1/3 year commitment | Cover 50% of baseline capacity |
| Compute savings plans | 20-30% | Flexible commitment | Cover variable compute |
| Right-sizing via VPA | 10-20% | None | Gradual rollout, observe 2 weeks |

### 21.2 Storage Optimization

| Strategy | Savings | Implementation |
|----------|---------|---------------|
| gp3 over io1 | 20% | Default storage class |
| S3 lifecycle policies | 40% | Infrequent Access after 30d, Glacier after 90d |
| EBS snapshot lifecycle | 50% | Delete snapshots after retention period |
| Qdrant compaction | 30% | Weekly compaction job |
| Log rotation + retention | 60% | Enforce max 30d hot, 90d cold |

### 21.3 GPU Cost Optimization

| Strategy | Savings | Details |
|----------|---------|---------|
| Model routing (cheaper models first) | 60% | SQLCoder-7b for 50% of queries |
| Continuous batching (vLLM) | 40% | Higher GPU utilization |
| GPU sharing (MPS/MIG) | 30% | Multiple models per GPU |
| Spot GPU (dev/staging) | 60% | Non-production only |
| Reserved GPU instances | 40% | Cover baseline with 1yr commitment |
| Scale-to-zero (off-peak) | 20% | Night/weekend scale-down |

### 21.4 Data Transfer Optimization

| Strategy | Savings | Implementation |
|----------|---------|---------------|
| Same-AZ traffic | 0 egress cost | Co-locate dependent services |
| CloudFront CDN | 80% egress savings | Static assets + API caching |
| S3 gateway endpoint | No NAT cost | VPC endpoint for S3 access |
| Compression (API responses) | 60% bandwidth | gzip all API responses > 1KB |

### 21.5 Monthly Cost Projection

| Category | Dev | Staging | Prod (100 tenants) | Prod (1K tenants) |
|----------|-----|---------|-------------------|-------------------|
| Compute (EC2/EKS) | $1,200 | $2,500 | $8,500 | $35,000 |
| GPU (MI300X) | $2,000 | $4,000 | $12,000 | $48,000 |
| Storage (EBS+S3) | $300 | $600 | $2,000 | $8,000 |
| Database (RDS) | $200 | $400 | $1,500 | $6,000 |
| Networking | $100 | $200 | $800 | $3,000 |
| Monitoring | $100 | $200 | $500 | $1,500 |
| **Total** | **$3,900** | **$7,900** | **$25,300** | **$101,500** |
| **Per tenant** | -- | -- | **$253** | **$101** |

### 21.6 Cost Alerts

| Alert | Threshold | Action |
|-------|-----------|--------|
| Daily GPU cost | > $500/day | Notify infra team, review model routing |
| Daily inference cost | > $200/day | Notify ML team, check for anomalies |
| Monthly compute | > 120% of budget | Review reserved instances, consider savings plans |
| Storage growth | > 20% month-over-month | Review retention policies, compact Qdrant |
| Cross-region data transfer | > $500/month | Review DR traffic, optimize replication |

---

## 22. Deployment Diagrams

### 22.1 SaaS (Shared Multi-Tenant)

```
                         Internet
                            |
                      [CloudFront CDN]
                            |
                    [Route53 DNS]
                            |
                   [ALB (HTTPS:443)]
                            |
              +-------------+-------------+
              |                           |
       [Traefik Ingress]           [Traefik Ingress]
              |                           |
      +-------+-------+           +-------+-------+
      |               |           |               |
[Public API:8100] [Frontend:3000] [KE API:8200]  (internal)
      |               |           |               |
      +-------+-------+           +-------+-------+
              |                           |
      [Query Pipeline]           [Knowledge Engine]
      +-- Intent Agent            +-- Metadata Store
      +-- Retrieval Agent         +-- Schema Store
      +-- Planner Agent           +-- Graph Store
      +-- Generator Agent         +-- Embedding Store
      +-- Validator Agent         +-- Context Store
      +-- Policy Enforcement      +-- Ontology Store
      +-- Executor                +-- Pattern Store
              |                           |
      +-------+-------+           +-------+-------+
      |               |           |               |
[PostgreSQL RDS] [Qdrant Cluster] [Redis Cache] [GPU Pool]
  (shared, RLS)   (shared cols)   (shared)    (AMD MI300X)
```

### 22.2 Dedicated Cloud (Per-Tenant)

```
                         Internet
                            |
                      [CloudFront CDN]
                            |
                    [Route53 DNS]
                            |
                   [ALB (HTTPS:443)]
                            |
              +-------------+-------------+
              |                           |
       [Traefik Ingress]           [Traefik Ingress]
              |                           |
      +-------+-------+           +-------+-------+
      |               |           |               |
[Public API:8100] [Frontend:3000] [KE API:8200]  (internal)
      |                           |
      +---------------------------+
              |           |
      [Tenant Router] (determines tenant_id)
              |
    +---------+---------+
    |         |         |
[T1 Pool] [T2 Pool] [T3 Pool]  (per-tenant compute)
    |         |         |
  [PG:T1]  [PG:T2]  [PG:T3]    (per-tenant RDS)
  [QD:T1]  [QD:T2]  [QD:T3]    (per-tenant Qdrant)
```

### 22.3 Customer VPC

```
                        Customer Cloud
+-------------------------------------------------------------------+
|  Customer VPC                                                      |
|                                                                    |
|  [Customer ALB] -> [SchemaIntern Services] -> [Customer RDS/Qdrant]   |
|       |                                                           |
|  [Customer DNS]                                                    |
|                                                                    |
|  Monitoring accessible only via VPC peering / VPN                 |
|  Upgrades via private registry (ECR pull-through)                 |
+-------------------------------------------------------------------+
```

### 22.4 On-Prem K8s

```
                        Customer DC
+-------------------------------------------------------------------+
|  Customer K8s Cluster                                              |
|                                                                    |
|  [nginx Ingress] -> [SchemaIntern Pods] -> [PG Operator] [Qdrant]    |
|       |                                      |                    |
|  [Customer DNS]                     [Local SSD / SAN Storage]     |
|                                                                   |
|  No Internet Access (air-gapped)                                  |
|  Updates via bundled tarball                                      |
|  Monitoring via local Prometheus/Grafana                          |
+-------------------------------------------------------------------+
```

### 22.5 Multi-Region DR (Enterprise)

```
                    us-east-1 (Primary)                  us-west-2 (DR)
+------------------------------------------------+  +------------------+
| [ALB] -> [EKS Prod]                            |  | [ALB]            |
|    |                                           |  |    |             |
| [RDS Primary] <---> [Cross-Region Replication] |  | [RDS Standby]    |
|    |                                           |  |                  |
| [Qdrant Primary] <-> [Qdrant Replica (async)]  |  | [Qdrant Replica] |
|    |                                           |  |                  |
| [S3 Bucket] -------> [S3 Cross-Region Repl] -- |  | [S3 Bucket]      |
|    |                                           |  |                  |
| Route53: Primary (weight 100)                  |  | Route53: DR (0)  |
+------------------------------------------------+  +------------------+
                            |
                    Route53 Health Check
                    Failover on 3 consecutive failures
```

### 22.6 CI/CD Pipeline

```
[GitHub] --> [Actions] --> [Build] --> [Test] --> [ECR]
    |            |            |          |           |
    |            |            |          |     +-----+-----+
    |            |            |          |     |           |
    |            |            |          |  [Dev Deploy]  |
    |            |            |          |     |          |
    |            |            |          |  [Integration Tests]
    |            |            |          |     |          |
    |            |            |          |  [Staging Deploy]
    |            |            |          |     |          |
    |            |            |          |  [E2E Tests]   |
    |            |            |          |     |          |
    |            |      [Approval Gate]  |  [Prod Deploy] |
    |            |            |          |     |          |
    |            |            |          |  [ArgoCD Sync] |
    |            |            |          |     |          |
    |            |            |          |  [Canary 10%]  |
    |            |            |          |     |          |
    |            |            |          |  [Rollout 100%]|
    +------------+------------+----------+-----+----------+
```

---

