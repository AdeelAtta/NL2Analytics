from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from schema_intelligence.connectors.base import ConnectorConfig, ConnectorRegistry
from schema_intelligence.connectors.bigquery import BigQueryConnector
from schema_intelligence.connectors.duckdb import DuckDBConnector
from schema_intelligence.connectors.mysql import MySQLConnector
from schema_intelligence.connectors.postgresql import PostgreSQLConnector
from schema_intelligence.connectors.snowflake import SnowflakeConnector
from schema_intelligence.sync.orchestrator import SyncOrchestrator

ConnectorRegistry.register("postgresql", PostgreSQLConnector)
ConnectorRegistry.register("mysql", MySQLConnector)
ConnectorRegistry.register("snowflake", SnowflakeConnector)
ConnectorRegistry.register("bigquery", BigQueryConnector)
ConnectorRegistry.register("duckdb", DuckDBConnector)

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])


class SyncConnectionRequest(BaseModel):
    db_type: str = "postgresql"
    host: str = "localhost"
    port: int = 5432
    database: str = ""
    username: str = ""
    password: str = ""
    ssl: bool = False


def _make_config(body: SyncConnectionRequest, timeout: int = 10) -> ConnectorConfig:
    return ConnectorConfig(
        host=body.host,
        port=body.port,
        database=body.database or body.db_type,
        username=body.username,
        password=body.password,
        ssl=body.ssl,
        timeout_seconds=timeout,
    )


@router.post("/test")
async def test_connection(
    body: SyncConnectionRequest,
    current_user: dict[str, str] = Depends(get_current_user),
) -> dict[str, Any]:
    if current_user.get("sub") == "anonymous":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    try:
        connector_cls = ConnectorRegistry.get_connector(body.db_type)
        connector = connector_cls()
        await connector.connect(_make_config(body, 10))
        await connector.close()
        return {"success": True, "data": {"status": "connected", "host": body.host}}
    except KeyError:
        return {"success": False, "error": f"Unsupported DB type: {body.db_type}"}
    except Exception as e:
        return {"success": False, "error": f"Connection failed: {str(e)[:200]}"}


@router.get("/status")
async def sync_status(
    current_user: dict[str, str] = Depends(get_current_user),
) -> dict[str, Any]:
    if current_user.get("sub") == "anonymous":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    tenant_id = current_user.get("tenant_id", "demo")
    from ke.services.schema_registry import get_schema, get_connection
    schema = get_schema(tenant_id)
    conn = get_connection(tenant_id)
    return {
        "success": True,
        "data": {
            "synced": schema is not None,
            "connection": conn,
            "table_count": len(schema.get("tables", [])) if schema else 0,
        },
    }


def _infer_relationships(tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rels: list[dict[str, Any]] = []
    table_names = {t["name"].lower() for t in tables}
    for tbl in tables:
        tbl_name = tbl["name"].lower()
        for col in tbl.get("columns", []):
            col_name = col.get("name", "")
            if col_name.endswith("_id") and col_name != "id":
                ref_table = col_name[:-3]
                if ref_table in table_names:
                    rels.append({
                        "source_table": tbl_name,
                        "source_column": col_name,
                        "target_table": ref_table,
                        "target_column": "id",
                        "relationship_type": "foreign_key",
                    })
    return rels


@router.post("/extract")
async def sync_and_extract(
    body: SyncConnectionRequest,
    current_user: dict[str, str] = Depends(get_current_user),
) -> dict[str, Any]:
    if current_user.get("sub") == "anonymous":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    tenant_id = current_user.get("tenant_id", "default")
    try:
        orchestrator = SyncOrchestrator()
        result = await orchestrator.sync(_make_config(body, 30), db_type=body.db_type)
        from schema_intelligence.sync.models import SyncChangeType

        added_tables = [c.table for c in result.changes if c.change_type == SyncChangeType.ADDED]
        changed_tables = [c.table for c in result.changes if c.change_type == SyncChangeType.CHANGED]

        tables_out = []
        all_columns: list[dict[str, Any]] = []
        for table in added_tables + changed_tables:
            cols = []
            for c in table.columns:
                col_data = {
                    "name": c.name,
                    "data_type": c.data_type,
                    "is_primary_key": c.is_primary_key,
                    "is_nullable": c.is_nullable,
                    "ordinal_position": getattr(c, "ordinal_position", 0),
                    "table_name": table.name,
                }
                cols.append(col_data)
                all_columns.append(col_data)
            tables_out.append({"name": table.name, "columns": cols})

        # Infer relationships from FK-like column names
        inferred_rels = _infer_relationships(tables_out)
        all_relationships = inferred_rels

        # Store in persistent schema registry (JSON file fallback)
        from ke.services.schema_registry import store_schema as store_registry
        store_registry(tenant_id, tables_out, all_columns, all_relationships)

        # Save connection details for later use
        from ke.services.schema_registry import store_connection
        store_connection(tenant_id, {
            "db_type": body.db_type,
            "host": body.host,
            "port": body.port,
            "database": body.database,
            "username": body.username,
            "ssl": body.ssl,
            "synced_at": str(datetime.now(UTC)),
            "table_count": len(tables_out),
        })

        # Store in PostgreSQL if available
        await _store_in_postgres(tenant_id, tables_out, all_columns)

        return {
            "success": True,
            "data": {
                "tables": tables_out,
                "added": len(added_tables),
                "changed": len(changed_tables),
                "removed": sum(1 for c in result.changes if c.change_type == SyncChangeType.REMOVED),
            },
        }
    except KeyError:
        return {"success": False, "error": f"Unsupported DB type: {body.db_type}"}
    except Exception as e:
        return {"success": False, "error": f"Sync failed: {str(e)[:300]}"}


async def _store_in_postgres(tenant_id: str, tables: list[dict[str, Any]], columns: list[dict[str, Any]]) -> None:
    try:
        from app.core.database import get_session
        from ke.models.schema import (
            Column as ColumnModel,
        )
        from ke.models.schema import (
            DatabaseConfig as DatabaseConfigModel,
        )
        from ke.models.schema import (
            Table as TableModel,
        )
        from ke.models.schema import (
            Tenant as TenantModel,
        )
        from ke.stores.schema.repository import (
            ColumnRepository,
            DatabaseConfigRepository,
            TableRepository,
            TenantRepository,
        )

        async with get_session() as session:
            # 1. Upsert tenant
            tenant_repo = TenantRepository(session)
            existing = await tenant_repo.get(tenant_id)
            if existing is None:
                await tenant_repo.create(TenantModel(
                    id=tenant_id, name=f"Tenant {tenant_id[:8]}",
                    slug=tenant_id[:50], tier="starter", status="active",
                    created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
                ))

            # 2. Upsert database config
            db_repo = DatabaseConfigRepository(session)
            db_id = f"db-{tenant_id}"
            existing_db = await db_repo.get(db_id)
            if existing_db is None:
                await db_repo.create(DatabaseConfigModel(
                    id=db_id, tenant_id=tenant_id, name="Synced Database",
                    db_type="postgresql", connection_hash=tenant_id,
                    host="", sync_status="synced", table_count=len(tables),
                    is_active=True, created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
                ))

            # 3. Upsert tables + columns
            table_repo = TableRepository(session)
            col_repo = ColumnRepository(session)

            for tbl in tables:
                table_id = f"tbl-{tenant_id}-{tbl['name']}"
                existing_tbl = await table_repo.get(table_id)
                if existing_tbl is None:
                    await table_repo.create(TableModel(
                        id=table_id, schema_id="synced", name=tbl["name"],
                        description=f"{len(tbl['columns'])} columns",
                        is_active=True,
                    ))
                for col in tbl.get("columns", []):
                    col_id = f"col-{tenant_id}-{tbl['name']}-{col['name']}"
                    existing_col = await col_repo.get(col_id)
                    if existing_col is None:
                        await col_repo.create(ColumnModel(
                            id=col_id, table_id=table_id, name=col["name"],
                            data_type=col.get("data_type", "unknown"),
                            ordinal_position=col.get("ordinal_position", 0),
                            is_nullable=col.get("is_nullable", True),
                            is_primary_key=col.get("is_primary_key", False),
                        ))

    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Could not store schema in PostgreSQL: %s", e)
