from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.auth.dependencies import get_current_user
from app.core.database import get_session
from ke.services.schema_registry import get_schema
from ke.stores.schema.repository import (
    ColumnRepository,
    DatabaseConfigRepository,
    TableRepository,
)

router = APIRouter(prefix="/api/v1/schema", tags=["schema"])


def _auth(current_user: dict[str, str]) -> str:
    if current_user.get("sub") == "anonymous":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return current_user.get("tenant_id", "demo")


def _empty(page=1, ps=50):
    return {"success": True, "data": [], "meta": {"page": page, "page_size": ps, "total": 0}}


async def _run(fn):
    try:
        async with get_session() as session:
            return await fn(session)
    except Exception:
        return None


def _registry_tables(tenant_id: str, page: int, page_size: int) -> dict[str, Any] | None:
    schema = get_schema(tenant_id)
    if not schema or not schema.get("tables"):
        return None
    tables = schema["tables"]
    start = (page - 1) * page_size
    end = start + page_size
    page_data = tables[start:end]
    return {
        "success": True,
        "data": [
            {"id": f"reg-{t['name']}", "name": t["name"], "description": f"{len(t['columns'])} columns", "schema_name": ""}
            for t in page_data
        ],
        "meta": {"page": page, "page_size": page_size, "total": len(tables)},
    }


@router.get("/tables")
async def list_tables(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: dict[str, str] = Depends(get_current_user),
) -> dict[str, Any]:
    tenant_id = _auth(current_user)

    reg = _registry_tables(tenant_id, page, page_size)
    if reg:
        return reg

    async def _list(session):
        from shared.models.pagination import PaginationParams
        repo = TableRepository(session)
        items, total = await repo.list(filters={"is_active": True}, pagination=PaginationParams(page=page, page_size=page_size))
        return [
            {"id": t.id, "name": t.name, "description": t.description, "schema_name": ""}
            for t in items
        ], total

    result = await _run(_list)
    if result is None:
        return _empty(page, page_size)
    items, total = result
    return {"success": True, "data": items, "meta": {"page": page, "page_size": page_size, "total": total}}


@router.get("/tables/{table_id}")
async def get_table(
    table_id: str,
    current_user: dict[str, str] = Depends(get_current_user),
) -> dict[str, Any]:
    tenant_id = _auth(current_user)

    schema = get_schema(tenant_id)
    if schema and schema.get("tables"):
        for t in schema["tables"]:
            if t["name"] == table_id or f"reg-{t['name']}" == table_id:
                return {
                    "success": True,
                    "data": {
                        "id": table_id,
                        "name": t["name"],
                        "description": "",
                        "columns": [
                            {
                                "id": f"col-{c['name']}",
                                "name": c["name"],
                                "data_type": c["data_type"],
                                "is_nullable": c.get("is_nullable", True),
                                "is_primary_key": c.get("is_primary_key", False),
                                "description": "",
                            }
                            for c in t.get("columns", [])
                        ],
                    },
                }

    async def _get(session):
        repo = TableRepository(session)
        table = await repo.get(table_id)
        if table is None:
            return None
        col_repo = ColumnRepository(session)
        columns, _ = await col_repo.list(filters={"table_id": table_id})
        return {
            "id": table.id, "name": table.name, "description": table.description,
            "columns": [
                {"id": c.id, "name": c.name, "data_type": c.data_type,
                 "is_nullable": c.is_nullable, "is_primary_key": c.is_primary_key,
                 "description": c.description}
                for c in columns
            ],
        }

    result = await _run(_get)
    if result is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"success": True, "data": result}


@router.get("/databases")
async def list_databases(
    request: Request,
    current_user: dict[str, str] = Depends(get_current_user),
) -> dict[str, Any]:
    tenant_id = _auth(current_user)

    schema = get_schema(tenant_id)
    if schema and schema.get("tables"):
        return {
            "success": True,
            "data": [{"id": "synced-db", "name": "Synced Database", "db_type": "postgresql", "sync_status": "synced"}],
        }

    async def _list(session):
        repo = DatabaseConfigRepository(session)
        items = await repo.list_by_tenant(tenant_id)
        return [{"id": d.id, "name": d.name, "db_type": d.db_type, "sync_status": d.sync_status} for d in items]

    result = await _run(_list)
    return {"success": True, "data": result or []}


@router.get("/search")
async def search_schema(
    request: Request,
    q: str = Query("", min_length=1),
    current_user: dict[str, str] = Depends(get_current_user),
) -> dict[str, Any]:
    _auth(current_user)
    ql = q.lower()

    async def _search(session):
        repo = TableRepository(session)
        items, _ = await repo.list(filters={"is_active": True})
        return [
            {"id": t.id, "name": t.name, "type": "table", "description": t.description}
            for t in items if ql in t.name.lower() or (t.description and ql in t.description.lower())
        ]

    result = await _run(_search)
    return {"success": True, "data": (result or [])[:20]}
