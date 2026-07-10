# TASK-012 Verification: Schema Versioning Logic

## Deliverables
- `backend/ke/models/schema.py`: Added `SchemaChangeType` (enum), `SchemaChange`, `SchemaVersion`
- `backend/ke/stores/schema/versioning.py`: `SchemaVersionOrm` + `VersioningService` with DDL diff
- `backend/alembic/versions/002_create_schema_versions.py`: Migration for `schema_versions` table
- `backend/tests/test_versioning.py`: 18 unit tests
- `backend/pyproject.toml`: Added `sqlglot>=25.0.0` dependency

## Results
- **Tests**: 18/18 passed (126 total across project)
- **Ruff**: clean
- **Mypy**: 19 pre-existing errors in repository.py (not introduced by this task)

## VersioningService API
| Method | Description |
|--------|-------------|
| `detect_changes(schema_id, new_ddl, old_ddl, triggered_by)` | Hash-compare DDL, classify diffs, increment version, store snapshot |
| `get_version_history(schema_id, limit=50)` | List versions newest-first |
| `get_version(schema_id, version)` | Get specific version |

## Change Detection
- DDL hashes computed with SHA256 on normalized whitespace
- `_classify_change` uses sqlglot AST diff to detect `COLUMN_ADDED`, `COLUMN_DROPPED`, and type changes
- Initial DDL detection → `TABLE_ADDED`
- Parse errors → fallback `COLUMN_TYPE_CHANGED` with error note
- Identical DDLs (hash match) → no change recorded (0 changes stored)

## Migration
- `002_create_schema_versions.py` creates `schema_store.schema_versions` table
- FK to `schema_infos(id)`, unique constraint on `(schema_id, version)`
- RLS policy via inherited tenant isolation
- SQL verified: upgrade and downgrade both generate correct SQL
