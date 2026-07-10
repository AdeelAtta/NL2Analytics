from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient

from app.core.database import get_qdrant
from ke.api.routes.schema import _get_column_repo, _get_table_repo
from ke.api.schemas import (
    KEErrorCode,
    KEResponse,
    error_response,
    success_response,
)
from ke.services.query import QueryService
from ke.stores.schema.repository import ColumnRepository, TableRepository
from ke.stores.vector.embedding import EmbeddingService
from ke.stores.vector.repository import VectorRepository

router = APIRouter(tags=["query"])


class ContextQuery(BaseModel):
    question: str
    limit: int = 10
    score_threshold: float | None = None


class DDLRenderRequest(BaseModel):
    table_ids: list[str]


async def _get_query_service(
    qdrant: AsyncQdrantClient = Depends(get_qdrant),
    table_repo: TableRepository = Depends(_get_table_repo),
    column_repo: ColumnRepository = Depends(_get_column_repo),
) -> QueryService:
    vector_repo = VectorRepository(qdrant)
    return QueryService(
        vector_repo=vector_repo,
        embedding_service=EmbeddingService(),
        table_repo=table_repo,
        column_repo=column_repo,
    )


@router.post("/context", response_model=KEResponse[dict])
async def search_context(
    request: Request,
    payload: ContextQuery,
    service: QueryService = Depends(_get_query_service),
):
    tenant_id = getattr(request.state, "tenant_id", "default")
    try:
        result = await service.search_context(
            question=payload.question,
            tenant_id=tenant_id,
            limit=payload.limit,
            score_threshold=payload.score_threshold,
        )
        return success_response(result)
    except Exception as e:
        return error_response(
            KEErrorCode.EMBEDDING_SERVICE_UNAVAILABLE,
            {"question": payload.question, "error": str(e)},
        )


@router.get("/context/table/{table_id}", response_model=KEResponse[dict])
async def get_table_context(
    table_id: str,
    service: QueryService = Depends(_get_query_service),
):
    try:
        result = await service.get_table_context(table_id=table_id)
        if result is None:
            return error_response(KEErrorCode.ENTITY_NOT_FOUND, {"id": table_id})
        return success_response(result)
    except Exception as e:
        return error_response(
            KEErrorCode.INTERNAL_ERROR,
            {"table_id": table_id, "error": str(e)},
        )


@router.post("/render-ddl", response_model=KEResponse[dict])
async def render_ddl(
    payload: DDLRenderRequest,
    service: QueryService = Depends(_get_query_service),
):
    try:
        result = await service.render_ddl(table_ids=payload.table_ids)
        return success_response({"ddl": result})
    except Exception as e:
        return error_response(
            KEErrorCode.INTERNAL_ERROR,
            {"error": str(e)},
        )


@router.get("/discover", response_model=KEResponse[dict])
async def discover_schemas(
    request: Request,
    service: QueryService = Depends(_get_query_service),
):
    tenant_id = getattr(request.state, "tenant_id", "default")
    try:
        databases = await _discover_for_tenant(tenant_id, service)
        return success_response(databases)
    except Exception as e:
        return error_response(
            KEErrorCode.INTERNAL_ERROR,
            {"error": str(e)},
        )


async def _discover_for_tenant(tenant_id: str, service: QueryService) -> list[dict]:
    return [{"tenant_id": tenant_id, "note": "Use /v1/ke/schema endpoints for full discovery"}]
