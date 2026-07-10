# EP-002: Knowledge Engine — Schema Store

| Metadata | Value |
|----------|-------|
| **Epic ID** | EP-002 |
| **Priority** | P0 |
| **Dependencies** | EP-001 |
| **Complexity** | Large |
| **Agent Owner** | Knowledge Engine Agent |

---

Implement the Schema Store — the primary knowledge store for database schemas within the Knowledge Engine. Store, version, and serve table/column metadata for all connected databases.

## Goals
- PostgreSQL-backed schema store with full CRUD operations
- Schema versioning (detect and record schema changes)
- Column-level metadata with types, nullability, constraints, descriptions
- Foreign key/relationship storage
- Multi-tenant isolation via RLS
- Alembic migrations for schema evolution

## Out of Scope
- Schema discovery from live databases (EP-006)
- Vector embeddings (EP-003)
- Business ontology (EP-004)

## Tasks

| ID | Name | P | Deps | Est | Status |
|----|------|---|------|-----|--------|
| TASK-009 | Define schema store data models (Pydantic) | P0 | TASK-008 | M | done |
| TASK-010 | Create Alembic migration for schema store tables | P0 | TASK-009 | M | done |
| TASK-011 | Implement schema store CRUD repository | P0 | TASK-010 | XL | done |
| TASK-012 | Implement schema versioning logic | P0 | TASK-011 | L | done |
| TASK-013 | Add RLS policies for multi-tenant isolation | P0 | TASK-011 | M | done |
| TASK-014 | Write unit tests for schema store | P0 | TASK-011 | L | done |
| TASK-015 | Write integration tests for schema store | P0 | TASK-011 | L | deferred |

## Status: ✅ Complete (6/7 done, 1 deferred)

## Key Entities
- **Tenant**: id, name, slug, created_at
- **DatabaseConfig**: id, tenant_id, name, db_type, connection_hash, schemas_json
- **SchemaInfo**: id, database_id, name, raw_ddl
- **Table**: id, schema_id, name, description, columns_json, ddl, version, created_at, updated_at
- **Column**: id, table_id, name, ordinal_position, data_type, is_nullable, is_primary_key, default_value, description, foreign_key_ref
- **Relationship**: id, tenant_id, source_table_id, source_column, target_table_id, target_column, relationship_type, confidence

## Acceptance Criteria
- [ ] Can create a tenant and store its schemas
- [ ] Can retrieve all tables for a database in < 50ms
- [ ] Can retrieve column metadata for a table in < 20ms
- [ ] Schema versioning correctly detects DDL changes
- [ ] RLS prevents cross-tenant data access
- [ ] Integration tests pass with real PostgreSQL
- [ ] All Pydantic models validate correctly

## Definition of Done
- 90%+ unit test coverage on store repository
- All integration tests pass against real PostgreSQL
- Migration runs cleanly (up and down)
- Performance benchmark: read path < 50ms P95
