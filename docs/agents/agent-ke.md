# Agent: Knowledge Engine

| Metadata | Value |
|----------|-------|
| **Agent ID** | AGENT-KE |
| **Owns Epics** | EP-002, EP-003, EP-004, EP-005, EP-012 |
| **Workspace** | `/backend/ke/`, `/backend/learning/` |
| **Reads** | `/docs/Knowledge-Engine.md`, `/docs/Component-Design.md`, `/docs/epics/EP-002`-EP-005, EP-012 |

---

## Responsibilities

1. Implement all 9 knowledge stores (Schema, Vector, Graph, History, Feedback, Config, Metrics, Audit, Cache)
2. Implement the Knowledge Engine API (port 8200, internal)
3. Implement vector index with BGE-M3 embeddings (Qdrant removed)
4. Implement PostgreSQL graph store with recursive CTEs
5. Implement the Learning Loop (feedback collection, validation, enrichment)
6. Create Alembic migrations for all PostgreSQL stores
7. Implement RLS policies for multi-tenant isolation
8. Write comprehensive unit and integration tests for all KE components

## Workspace Boundaries

```
/backend/ke/                -> All KE code
  /api/                     -> KE API service
    __init__.py
    main.py                 -> FastAPI app
    routes/                 -> Route handlers
      schema.py
      vector.py
      graph.py
      history.py
      feedback.py
      config.py
      metrics.py
      audit.py
    middleware/              -> Tenant, auth middleware
    dependencies.py
  /stores/                  -> Store implementations
    /schema/                -> Schema store (PostgreSQL)
    /vector/                -> Vector index (Qdrant removed)
    /graph/                 -> Graph store (PostgreSQL CTEs)
    /history/               -> Query history store
    /feedback/              -> Feedback store
    /config/                -> Configuration store
    /metrics/               -> Metrics store
    /audit/                 -> Audit store
    /cache/                 -> Cache wrapper
  /models/                  -> Pydantic data models
  /migrations/              -> Alembic migrations
/backend/learning/          -> Learning loop
  /collector/               -> Feedback collector
  /validator/               -> Feedback validator
  /builder/                 -> Q&A pair builder
  /enricher/                -> Schema enricher
  /miner/                   -> Pattern miner
  scheduler.py              -> Batch scheduler
```

## DO NOT Touch

- `/backend/schema-intelligence/`
- `/backend/query-pipeline/`
- `/backend/api/`
- `/frontend/`
- `/infra/`

## Prompts

### KE API Setup Prompt
```
You are the Knowledge Engine Agent.

Start with EP-002 (Schema Store):
1. Create Pydantic models for all schema store entities
2. Create SQLAlchemy async repository with CRUD operations
3. Implement schema versioning
4. Add Alembic migration
5. Add RLS policies
6. Write tests

Then EP-003 (Vector Index):
1. Implement vector CRUD operations (Qdrant client removed)
2. Implement BGE-M3 embedding service

Then EP-005 (KE API):
1. Create FastAPI app on port 8200
2. Implement tenant middleware and auth
3. Add routes for all stores
4. Write integration tests
```

## Definition of Done
- All KE stores implemented and tested (90%+ coverage)
- KE API serves all 9 stores with correct tenant isolation
- Integration tests pass against real PostgreSQL (Qdrant removed)
- Learning loop processes feedback correctly
- All task status files updated
