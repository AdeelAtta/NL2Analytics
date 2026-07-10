# EP-006: Schema Intelligence Pipeline

Epic ID: **EP-006** | Priority: **P0** | Dependencies: **EP-002, EP-003** | Complexity: **XL** | Agent: **Schema Intelligence Agent**

---

Implement the Schema Intelligence Pipeline — the subsystem that connects to live databases, introspects schemas, generates semantic descriptions, infers relationships, creates embeddings, and populates the Knowledge Engine.

## Goals
- Pluggable database connectors (PG, MySQL, Snowflake, BigQuery, DuckDB)
- DDL parser for schema extraction
- LLM-based description generation (Qwen2.5-72B)
- Relationship inference (FK detection + heuristic suggestions)
- Embedding generation for schema elements
- Incremental sync (detect changes, re-embed only changed items)

## Out of Scope
- Business ontology generation (EP-004)
- Query history patterns (EP-007)
- Real-time schema change detection (polling-based in MVP)

## Tasks

| ID | Name | P | Deps | Est |
|----|------|---|---|-----|
| TASK-043 | Implement database connector interface | P0 | TASK-008 | M | ✅ Done |
| TASK-044 | Implement PostgreSQL connector | P0 | TASK-043 | M | ✅ Done |
| TASK-045 | Implement MySQL connector | P1 | TASK-043 | M |
| TASK-046 | Implement Snowflake connector | P1 | TASK-043 | M |
| TASK-047 | Implement BigQuery connector | P1 | TASK-043 | M |
| TASK-048 | Implement DuckDB connector | P2 | TASK-043 | M |
| TASK-049 | Build DDL parser (sqlglot-based schema extraction) | P0 | TASK-043 | L | ✅ Done |
| TASK-050 | Implement LLM description annotator | P0 | TASK-049 | XL | ✅ Done |
| TASK-051 | Implement relationship inference engine | P0 | TASK-049 | L | ✅ Done |
| TASK-052 | Build incremental sync orchestrator | P0 | TASK-050 | XL | ✅ Done |
| TASK-053 | Implement schema-to-embedding pipeline | P0 | TASK-050, EP-003 | L | ✅ Done |
| TASK-054 | Implement metadata-to-KE sync | P0 | TASK-052, EP-005 | L |
| TASK-055 | Write unit and integration tests | P0 | TASK-050 | XL |

## Acceptance Criteria
- PostgreSQL connector extracts full schema in < 10s for 200-table DB
- LLM annotator generates descriptions for 50 columns in < 30s (batch)
- Relationship inference detects at least 80% of actual foreign key relationships
- Incremental sync detects changed tables and re-embeds only those
- All connectors implement the same interface
- Schema-to-embedding pipeline processes 200 tables in < 2 minutes

## Definition of Done
- Schema sync completes end-to-end: DB connection -> schema extraction -> description -> embedding -> KE store
- Integration tests against real PostgreSQL instance
- Performance benchmarks meet targets
- Connector interface documented
