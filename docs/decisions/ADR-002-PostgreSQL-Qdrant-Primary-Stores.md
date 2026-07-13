# ADR-002: PostgreSQL + Qdrant as Primary Knowledge Stores (Qdrant later removed during cleanup)

| Metadata | Value |
|----------|-------|
| **ADR ID** | ADR-002 |
| **Date** | 2026-07-10 |
| **Status** | Accepted |
| **Supersedes** | — |

---

## Context

The Knowledge Engine requires persistent storage for structured data, graph relationships, vector embeddings, and cache. Multiple storage technologies are available, each with different trade-offs for performance, operational complexity, and deployment flexibility.

## Decision

Use PostgreSQL for structured + graph data and Qdrant for vector search. Redis for cache/queues. No dedicated graph DB in MVP.

- **PostgreSQL**: Structured data, JSONB for semi-structured, recursive CTEs for graph traversal (sufficient for max 5-7 hop depth)
- **Qdrant**: Vector search with filtered search (tenant + database + data type filters before semantic search)
- **Redis**: Low-latency cache and message queues

## Rationale

PostgreSQL handles structured data, JSONB for semi-structured, and recursive CTEs provide sufficient graph traversal for our depth requirements (schemas rarely exceed 5-7 hop relationships). Qdrant performs best on filtered vector search benchmarks — the enterprise use case requires filtering by tenant + database + data type before semantic search. Redis provides low-latency cache for hot data.

All three are self-hostable, meeting the deployment-agnostic requirement.

## Consequences

### Positive
- PostgreSQL is mature, well-understood, and battle-tested for enterprise workloads
- Qdrant has best filtered vector search performance in benchmarks (critical for multi-tenant)
- All three stores are self-hostable (no cloud API dependency)
- Recursive CTEs eliminate need for Neo4j in MVP
- Redis is ubiquitous with well-known operational patterns

### Negative
- No native graph query language (Cypher) — recursive CTEs are more verbose
- PostgreSQL recursive CTE performance degrades at 10+ hop depth (acceptable for our 5-7 hop max)
- Managing 3 storage systems adds operational complexity vs single system
- Not a single query interface — applications must know which store to query

## Alternatives Considered

| Alternative | Reason for Rejection |
|-------------|---------------------|
| Neo4j | Over-engineered for MVP; adds operational complexity; PostgreSQL CTEs sufficient for MVP graph depth |
| Pinecone | Cloud-only — violates deployment-agnostic principle |
| pgvector alone | Performance 3-10x slower than Qdrant for filtered search at scale |
| Single PostgreSQL with everything | Vector search performance doesn't scale for our workload |
| Cloud-managed stores | Violates deployment-agnostic principle; on-prem/air-gapped impossible |

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| PostgreSQL recursive CTE performance degrades at schema depth > 7 hops | Low | Medium | Schema depth rarely exceeds 5-7 hops in practice; monitoring alerts on CTE execution time; Neo4j as future upgrade path |
| Qdrant collection count at 10K+ tenants exceeds recommended limits | Medium | Medium | Qdrant supports 100K+ collections in recent versions; monitor collection count; implement collection lifecycle management (archive inactive tenants) |
| Redis memory exhaustion from unbounded cache growth | Medium | High | Cache TTL policies; maxmemory eviction (allkeys-lru); memory usage alerting at 75% capacity |
| Storage node failure causes KE unavailability during failover | Medium | High | PostgreSQL streaming replication; Qdrant cluster mode; Redis Sentinel/Cluster; all with automated failover |

## Trade-offs

- **Neo4j vs PostgreSQL CTEs for graph**: Neo4j provides native graph query language (Cypher) and better performance for deep traversals. PostgreSQL recursive CTEs are more verbose and slower at 10+ hop depth. MVP trade-off favors simplicity (no Neo4j ops). If schema depth exceeds 7 hops in production, Neo4j evaluation triggers
- **pgvector vs Qdrant**: pgvector eliminates the operational overhead of a second store but is 3-10x slower for filtered vector search at scale. Multi-tenant filtering (tenant_id + database_id) is the critical path — Qdrant's payload indexing makes this fast. Accepting the operational overhead of two stores for the performance critical path
- **Single PostgreSQL vs Citus cluster**: Single PostgreSQL writer is a bottleneck at >10K tenants. MVP trade-off favors simplicity (single PG). At scale, Citus distribution shards by tenant_id. Architecture supports this migration without component changes (ADR-004: only KE API changes)

## Related ADRs

- ADR-001: Knowledge Engine as Architectural Core (KE owns all store access)
- ADR-004: KE API Is the Only Internal Interface (stores accessed only through KE API)
- ADR-005: Self-Hosted Knowledge Stores Only (self-hosting requirement reinforces store choice)
- ADR-006: Tenant Isolation at Row/Collection Level (isolation strategy determines store usage pattern)

## References

- [System-Architecture.md](../System-Architecture.md) §4 (Data Stores), §9 (ADR Index)
- [Architecture-Review.md](../Architecture-Review.md) §10.2
- [Database-Specification.md](../specifications/Database-Specification.md)
- [Schema-Specification.md](../specifications/Schema-Specification.md) §3 (Knowledge Graph Schema)
