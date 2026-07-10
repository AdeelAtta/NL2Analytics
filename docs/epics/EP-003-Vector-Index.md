# EP-003: Knowledge Engine — Vector Index

| Metadata | Value |
|----------|-------|
| **Epic ID** | EP-003 |
| **Priority** | P0 |
| **Dependencies** | EP-001 |
| **Complexity** | Medium |
| **Agent Owner** | Knowledge Engine Agent |

---

Implement the vector index store for semantic search over schemas, queries, and business terminology using Qdrant.

## Goals
- Qdrant collection management (per-tenant collections)
- BGE-M3 embedding generation service
- CRUD operations on vector points with payload
- Hybrid search (dense + sparse via Qdrant's quantized vectors)
- Multi-tenant isolation via collection-per-tenant

## Out of Scope
- Embedding content generation (EP-006 creates the content to embed)
- Query-time retrieval logic (EP-007)
- Learning loop updates (EP-012)

## Tasks

| ID | Name | P | Deps | Est | Status |
|----|------|---|------|-----|--------|
| TASK-016 | Setup Qdrant client and connection pool | P0 | TASK-001 | M | done |
| TASK-017 | Implement BGE-M3 embedding service | P0 | TASK-001 | L | done |
| TASK-018 | Define vector point schemas (payload models) | P0 | TASK-016 | M | done |
| TASK-019 | Implement Qdrant CRUD repository | P0 | TASK-016 | L | done |
| TASK-020 | Implement per-tenant collection management | P0 | TASK-019 | M | done |
| TASK-021 | Implement hybrid search with score fusion | P1 | TASK-019 | L | done |
| TASK-022 | Write unit and integration tests | P0 | TASK-019 | L | done |

## Status: ✅ Complete

## Key Design Decisions
- 1024-dim BGE-M3 embeddings (dense) + SPLADE sparse vectors for hybrid search
- Payload includes: content type (schema/query/term), source id, tenant id, text snippet
- Collections named `tenant_{tenant_id}_embeddings`
- Replication factor: 2 for dev, 3 for prod

## Acceptance Criteria
- [ ] BGE-M3 model loads and generates embeddings in < 500ms per batch (100 texts)
- [ ] Qdrant CRUD operations complete in < 100ms P95
- [ ] Hybrid search returns relevant results with correct ranking
- [ ] Per-tenant collections are isolated (cross-tenant search returns nothing)
- [ ] Dense + sparse vectors stored correctly

## Definition of Done
- All CRUD operations benchmarked
- Integration tests pass against real Qdrant
- Embedding service produces correct-dimension vectors
