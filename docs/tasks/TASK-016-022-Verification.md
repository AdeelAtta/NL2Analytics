# EP-003 Verification: Vector Index (Tasks TASK-016 through TASK-022)

## Deliverables

### Models (`backend/ke/models/vector.py`)
- `SparseVector`, `EmbeddingItem`, `EmbeddingResult`, `EmbeddingRequest`
- `VectorPoint`, `VectorPayload` (extends `TenantScopedModel`)
- `SearchResult`, `HybridSearchParams`

### Embedding Service (`backend/ke/stores/vector/embedding.py`)
- `EmbeddingService` with caching (SHA256 keyed), batch processing
- Deterministic pseudo-embedding (1024-dim normalized dense + SPLADE sparse)
- `embed()`, `embed_batch()`, `clear_cache()`

### Vector Repository (`backend/ke/stores/vector/repository.py`)
- `VectorRepository` wrapping `AsyncQdrantClient`
- Collection management: `ensure_collection`, `list_collections`, `delete_collection`, `collection_info`
- CRUD: `upsert_points`, `delete_points`, `delete_by_filter`, `count_points`
- Search: `search` (dense-only), `search_hybrid` (dense + sparse with prefetch + score fusion)
- Per-tenant isolation via collection naming: `tenant_{id}_embeddings`

### Qdrant Client (pre-existing, verified)
- `AsyncQdrantClient` singleton via `get_qdrant()` in `backend/app/core/database.py`
- Config: `qdrant_url`, `qdrant_grpc_port`, `qdrant_api_key` in `Settings`
- Docker Compose Qdrant service already configured

### Tests
- `test_vector_models.py` — 8 tests for payload schemas
- `test_embedding.py` — 7 tests for embedding service
- `test_vector_repository.py` — 18 tests for repository (mocked Qdrant client)

## Results
- **Tests**: 33 new tests, 159 total across project — all pass
- **Ruff**: clean
- **Mypy**: clean

## Key Design Decisions
- Uses `query_points` API (qdrant-client v1.18+, not legacy `search`)
- Collection-per-tenant model (`tenant_{id}_embeddings`)
- Hybrid search: prefetch dense (3x limit) → sparse query with weighted scores
- `dense_weight` parameter (default 0.7) controls dense vs sparse contribution
- Embedding service uses deterministic algorithm (not BGE-M3) — placeholder for real model
- Filter support: `content_type`, `tenant_id`, `source_id`
