# Disaster Recovery Plan

**Project:** SchemaIntern | **Date:** 2026-07-11 | **Severity:** CRITICAL

---

## 1. Recovery Objectives

| Metric | Target | Measurement |
|--------|--------|-------------|
| RTO (Recovery Time Objective) | 4 hours | Time to restore full service after total outage |
| RPO (Recovery Point Objective) | 15 minutes | Maximum data loss acceptable |
| MTD (Maximum Tolerable Downtime) | 8 hours | Before business impact becomes unacceptable |

## 2. Failure Scenarios

### 2.1 Single Service Failure
**Example:** Backend pod crash-loops
**Impact:** Partial query failures
**RTO:** 5 minutes
**Action:** Kubernetes auto-restarts pod via Deployment. Check logs, fix config, rollout fix.

### 2.2 Database Failure (PostgreSQL)
**Impact:** Complete service unavailability
**RTO:** 30 minutes (with replica), 2 hours (from backup)
**Action:**
```
# Promote read replica
aws rds promote-read-replica --db-instance-identifier upl-prod-replica

# Or restore from backup
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier upl-prod-restored \
  --db-snapshot-identifier upl-prod-snapshot-latest
```

### 2.3 Cache Failure (Redis)
**Impact:** Performance degradation, session loss
**RTO:** 10 minutes
**Action:** ElastiCache auto-failover to replica node. Sessions recreated from scratch.

### 2.4 Vector Store Failure (Qdrant)
**Impact:** Semantic search unavailable, fallback to keyword-only retrieval
**RTO:** 1 hour
**Action:** Restart Qdrant container. Re-embed schemas from PostgreSQL via the Schema Embedding Pipeline.

### 2.5 Region Outage
**Impact:** Complete service unavailable in affected region
**RTO:** 4 hours
**Action:** Activate cross-region DR (see §5).

## 3. Backup Procedures

| Component | Method | Frequency | Retention | Location |
|-----------|--------|-----------|-----------|----------|
| PostgreSQL | Automated snapshots | Daily | 30 days | AWS RDS |
| PostgreSQL | WAL streaming to S3 | Continuous | 7 days | S3 `upl-db-wal/` |
| Redis | No persistent backup | — | — | Rebuild from PG data |
| Qdrant | Snapshot API | Daily | 7 days | EBS volume snapshots |
| K8s manifests | Git | On commit | Full history | GitHub |
| Terraform state | S3 backend | On apply | Full history | S3 `upl-terraform-state/` |
| Application config | `.env` in secrets manager | On change | — | AWS Secrets Manager |

### 3.1 PostgreSQL Backup Script
```bash
#!/bin/bash
# Manual backup trigger
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
aws rds create-db-snapshot \
  --db-instance-identifier upl-prod \
  --db-snapshot-identifier upl-prod-manual-${TIMESTAMP}

# Download backup locally
aws s3 cp s3://upl-db-backups/upl-prod-${TIMESTAMP}.dump .
```

### 3.2 Qdrant Backup
```bash
# Trigger snapshot via API
curl -X POST 'http://qdrant:6333/snapshots' \
  -H 'Content-Type: application/json' \
  -d '{"collection": "tenant_demo_embeddings"}'

# List snapshots
curl 'http://qdrant:6333/snapshots'
```

## 4. Restore Procedures

### 4.1 Full System Restore
```bash
# 1. Restore PostgreSQL
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier upl-prod-restored \
  --db-snapshot-identifier upl-prod-snapshot-latest

# 2. Point application to new DB
aws secretsmanager update-secret \
  --secret-id upl/prod/database \
  --secret-string "postgresql+asyncpg://user:pass@upl-prod-restored.xyz.us-east-1.rds.amazonaws.com:5432/schemaintern"

# 3. Roll Kubernetes pods to pick up new secrets
kubectl rollout restart deployment/backend -n schemaintern
kubectl rollout restart deployment/frontend -n schemaintern

# 4. Re-embed schemas into Qdrant
curl -X POST http://backend:8100/api/v1/connections/resync-all \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# 5. Verify health
curl http://backend:8100/api/v1/health/ready
```

### 4.2 Data Corruption Recovery
```bash
# 1. Identify the corruption point
# 2. Restore DB to point-in-time just before corruption
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier upl-prod \
  --target-db-instance-identifier upl-prod-pitr \
  --restore-time "2026-07-11T14:30:00"

# 3. Export corrupted data, re-import clean data
pg_dump -h upl-prod-pitr -U schemaintern schemaintern > clean_dump.sql
psql -h upl-prod -U schemaintern schemaintern < clean_dump.sql
```

## 5. Cross-Region Disaster Recovery

### 5.1 Architecture
```
Primary Region (us-east-1)          DR Region (us-west-2)
┌─────────────────────┐            ┌─────────────────────┐
│  EKS Cluster        │            │  EKS Cluster        │
│  RDS PostgreSQL     │───WAL──▶  │  RDS Read Replica   │
│  ElastiCache Redis  │            │  Redis (cold)       │
│  Qdrant (EC2)       │            │  Qdrant (cold)      │
│  Route53 (active)   │            │  Route53 (passive)  │
└─────────────────────┘            └─────────────────────┘
```

### 5.2 Failover Steps
```bash
# 1. Promote DR database
aws rds promote-read-replica \
  --db-instance-identifier upl-prod-dr-replica

# 2. Switch Route53 to DR region
aws route53 change-resource-record-sets \
  --hosted-zone-id ZONE_ID \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "app.schemaintern.io",
        "Type": "A",
        "AliasTarget": {
          "HostedZoneId": "DR_ALB_ZONE_ID",
          "DNSName": "dr-alb-123456.us-west-2.elb.amazonaws.com",
          "EvaluateTargetHealth": true
        }
      }
    }]
  }'

# 3. Scale up DR EKS
kubectl scale deployment backend --replicas=3 -n schemaintern
kubectl scale deployment frontend --replicas=3 -n schemaintern

# 4. Verify
curl https://app.schemaintern.io/api/v1/health/ready
```

## 6. Communication Plan

| Severity | Notification | Method | Within |
|----------|-------------|--------|--------|
| Critical (full outage) | All hands | PagerDuty + Slack | 5 min |
| High (degraded) | Engineering team | Slack | 15 min |
| Medium (partial) | Team lead | Slack DM | 1 hour |
| Low (cosmetic) | Next standup | In-person | 1 day |

## 7. Testing Schedule

| Test | Frequency | Success Criteria |
|------|-----------|-----------------|
| Backup integrity | Weekly | Restore to staging environment |
| Failover to DR | Monthly | Full traffic served from DR region < 30 min |
| Pod recovery | Every deploy | Pods healthy within 2 min of restart |
| Data restore | Quarterly | Full DB restore from backup completes in < 2 hours |

## 8. Runbook Locations

| Runbook | Location |
|---------|----------|
| Kubernetes operations | `docs/runbooks/k8s.md` |
| Database operations | `docs/runbooks/database.md` |
| Incident response | `docs/runbooks/incident-response.md` |
| Backup/restore | This document (§3-4) |
