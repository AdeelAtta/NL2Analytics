from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from ke.api.schemas import (
    KEErrorCode,
    KEListResponse,
    KEResponse,
    error_response,
    success_response,
)
from ke.models.schema import (
    Column as ColumnModel,
)
from ke.models.schema import (
    DatabaseConfig as DatabaseConfigModel,
)
from ke.models.schema import (
    Relationship as RelationshipModel,
)
from ke.models.schema import (
    SchemaInfo as SchemaInfoModel,
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
    RelationshipRepository,
    SchemaInfoRepository,
    TableRepository,
    TenantRepository,
)
from shared.models.pagination import PaginationParams

router = APIRouter(tags=["schema"])


async def _get_tenant_repo(session: AsyncSession = Depends(get_session)) -> TenantRepository:
    return TenantRepository(session)


async def _get_db_repo(session: AsyncSession = Depends(get_session)) -> DatabaseConfigRepository:
    return DatabaseConfigRepository(session)


async def _get_schema_repo(session: AsyncSession = Depends(get_session)) -> SchemaInfoRepository:
    return SchemaInfoRepository(session)


async def _get_table_repo(session: AsyncSession = Depends(get_session)) -> TableRepository:
    return TableRepository(session)


async def _get_column_repo(session: AsyncSession = Depends(get_session)) -> ColumnRepository:
    return ColumnRepository(session)


async def _get_rel_repo(session: AsyncSession = Depends(get_session)) -> RelationshipRepository:
    return RelationshipRepository(session)


@router.get("/tenants", response_model=KEListResponse[TenantModel])
async def list_tenants(
    page: int = 1,
    page_size: int = 50,
    repo: TenantRepository = Depends(_get_tenant_repo),
):
    pagination = PaginationParams(page=page, page_size=page_size)
    items, total = await repo.list(pagination=pagination)
    return KEListResponse[TenantModel](
        data=items,
        meta={
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": max(1, -(-total // page_size)),
        },
    )


@router.get("/tenants/{tenant_id}", response_model=KEResponse[TenantModel])
async def get_tenant(
    tenant_id: str,
    repo: TenantRepository = Depends(_get_tenant_repo),
):
    tenant = await repo.get(tenant_id)
    if tenant is None:
        return error_response(KEErrorCode.ENTITY_NOT_FOUND, {"id": tenant_id})
    return success_response(tenant)


@router.get("/tenants/by-slug/{slug}", response_model=KEResponse[TenantModel])
async def get_tenant_by_slug(
    slug: str,
    repo: TenantRepository = Depends(_get_tenant_repo),
):
    tenant = await repo.get_by_slug(slug)
    if tenant is None:
        return error_response(KEErrorCode.ENTITY_NOT_FOUND, {"slug": slug})
    return success_response(tenant)


@router.get("/databases", response_model=KEListResponse[DatabaseConfigModel])
async def list_databases(
    tenant_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
    repo: DatabaseConfigRepository = Depends(_get_db_repo),
):
    pagination = PaginationParams(page=page, page_size=page_size)
    if tenant_id:
        items, total = await repo.list(filters={"tenant_id": tenant_id}, pagination=pagination)
    else:
        items, total = await repo.list(pagination=pagination)
    return KEListResponse[DatabaseConfigModel](
        data=items,
        meta={
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": max(1, -(-total // page_size)),
        },
    )


@router.get("/databases/{db_id}", response_model=KEResponse[DatabaseConfigModel])
async def get_database(
    db_id: str,
    repo: DatabaseConfigRepository = Depends(_get_db_repo),
):
    db = await repo.get(db_id)
    if db is None:
        return error_response(KEErrorCode.ENTITY_NOT_FOUND, {"id": db_id})
    return success_response(db)


@router.get("/schemas", response_model=KEListResponse[SchemaInfoModel])
async def list_schemas(
    database_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
    repo: SchemaInfoRepository = Depends(_get_schema_repo),
):
    pagination = PaginationParams(page=page, page_size=page_size)
    if database_id:
        items, total = await repo.list(filters={"database_id": database_id}, pagination=pagination)
    else:
        items, total = await repo.list(pagination=pagination)
    return KEListResponse[SchemaInfoModel](
        data=items,
        meta={
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": max(1, -(-total // page_size)),
        },
    )


@router.get("/schemas/{schema_id}", response_model=KEResponse[SchemaInfoModel])
async def get_schema(
    schema_id: str,
    repo: SchemaInfoRepository = Depends(_get_schema_repo),
):
    schema = await repo.get(schema_id)
    if schema is None:
        return error_response(KEErrorCode.ENTITY_NOT_FOUND, {"id": schema_id})
    return success_response(schema)


@router.get("/tables", response_model=KEListResponse[TableModel])
async def list_tables(
    schema_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
    repo: TableRepository = Depends(_get_table_repo),
):
    pagination = PaginationParams(page=page, page_size=page_size)
    if schema_id:
        items, total = await repo.list(filters={"schema_id": schema_id}, pagination=pagination)
    else:
        items, total = await repo.list(pagination=pagination)
    return KEListResponse[TableModel](
        data=items,
        meta={
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": max(1, -(-total // page_size)),
        },
    )


@router.get("/tables/{table_id}", response_model=KEResponse[TableModel])
async def get_table(
    table_id: str,
    repo: TableRepository = Depends(_get_table_repo),
):
    table = await repo.get(table_id)
    if table is None:
        return error_response(KEErrorCode.ENTITY_NOT_FOUND, {"id": table_id})
    return success_response(table)


@router.get("/columns", response_model=KEListResponse[ColumnModel])
async def list_columns(
    table_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
    repo: ColumnRepository = Depends(_get_column_repo),
):
    pagination = PaginationParams(page=page, page_size=page_size)
    if table_id:
        items, total = await repo.list(filters={"table_id": table_id}, pagination=pagination)
    else:
        items, total = await repo.list(pagination=pagination)
    return KEListResponse[ColumnModel](
        data=items,
        meta={
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": max(1, -(-total // page_size)),
        },
    )


@router.get("/columns/{col_id}", response_model=KEResponse[ColumnModel])
async def get_column(
    col_id: str,
    repo: ColumnRepository = Depends(_get_column_repo),
):
    col = await repo.get(col_id)
    if col is None:
        return error_response(KEErrorCode.ENTITY_NOT_FOUND, {"id": col_id})
    return success_response(col)


@router.get("/relationships", response_model=KEListResponse[RelationshipModel])
async def list_relationships(
    tenant_id: str | None = None,
    source_table_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
    repo: RelationshipRepository = Depends(_get_rel_repo),
):
    pagination = PaginationParams(page=page, page_size=page_size)
    filters = {}
    if tenant_id:
        filters["tenant_id"] = tenant_id
    if source_table_id:
        filters["source_table_id"] = source_table_id
    items, total = await repo.list(filters=filters or None, pagination=pagination)
    return KEListResponse[RelationshipModel](
        data=items,
        meta={
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": max(1, -(-total // page_size)),
        },
    )


@router.get("/relationships/{rel_id}", response_model=KEResponse[RelationshipModel])
async def get_relationship(
    rel_id: str,
    repo: RelationshipRepository = Depends(_get_rel_repo),
):
    rel = await repo.get(rel_id)
    if rel is None:
        return error_response(KEErrorCode.ENTITY_NOT_FOUND, {"id": rel_id})
    return success_response(rel)
