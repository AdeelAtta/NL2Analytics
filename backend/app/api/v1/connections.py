from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.core.database import get_session
from ke.stores.schema.repository import DatabaseConfigRepository

router = APIRouter(prefix="/api/v1/connections", tags=["connections"])

DB_TYPES = ["postgresql", "mysql", "snowflake", "bigquery", "duckdb"]


class CreateConnectionRequest(BaseModel):
    name: str
    db_type: str = "postgresql"
    host: str = "localhost"
    port: int = 5432
    database_name: str = ""
    username: str = ""
    password: str = ""
    ssl_enabled: bool = False


@router.post("")
async def create_connection(
    request: Request,
    body: CreateConnectionRequest,
    current_user: dict[str, str] = Depends(get_current_user),
) -> dict[str, Any]:
    if current_user.get("sub") == "anonymous":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Authentication required")

    if body.db_type not in DB_TYPES:
        raise HTTPException(status_code=422,
                            detail=f"Unsupported DB type. Supported: {', '.join(DB_TYPES)}")

    tenant_id = getattr(request.state, "tenant_id", current_user.get("tenant_id", "demo"))

    import hashlib, uuid
    from datetime import UTC, datetime

    from ke.models.schema import DatabaseConfig as DatabaseConfigModel, Tenant as TenantModel
    from ke.stores.schema.repository import TenantRepository

    conn_str = f"{body.db_type}://{body.username}:{body.password}@{body.host}:{body.port}/{body.database_name}"
    connection_hash = hashlib.sha256(conn_str.encode()).hexdigest()

    async with get_session() as session:
        tenant_repo = TenantRepository(session)
        existing_tenant = await tenant_repo.get(tenant_id)
        if existing_tenant is None:
            await tenant_repo.create(TenantModel(
                id=tenant_id, name=f"Tenant {tenant_id[:8]}",
                slug=tenant_id[:50], tier="starter", status="active",
                created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
            ))

        repo = DatabaseConfigRepository(session)
        entry = await repo.create(DatabaseConfigModel(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name=body.name,
            db_type=body.db_type,
            connection_hash=connection_hash,
            host=body.host,
            port=body.port,
            database_name=body.database_name,
            username=body.username,
            ssl_enabled=body.ssl_enabled,
            sync_status="pending",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ))

    return {
        "success": True,
        "data": {
            "id": entry.id,
            "name": entry.name,
            "db_type": entry.db_type,
            "host": entry.host,
            "port": entry.port,
            "database_name": entry.database_name,
            "sync_status": "pending",
        },
    }


@router.get("")
async def list_connections(
    request: Request,
    current_user: dict[str, str] = Depends(get_current_user),
) -> dict[str, Any]:
    if current_user.get("sub") == "anonymous":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Authentication required")

    tenant_id = getattr(request.state, "tenant_id", current_user.get("tenant_id", "demo"))

    async with get_session() as session:
        repo = DatabaseConfigRepository(session)
        items = await repo.list_by_tenant(tenant_id)

    return {
        "success": True,
        "data": [
            {
                "id": db.id,
                "name": db.name,
                "db_type": db.db_type,
                "host": db.host,
                "port": db.port,
                "database_name": db.database_name,
                "sync_status": db.sync_status,
                "table_count": db.table_count,
                "last_synced_at": db.last_synced_at.isoformat() if db.last_synced_at else None,
                "created_at": db.created_at.isoformat(),
            }
            for db in items
        ],
    }
