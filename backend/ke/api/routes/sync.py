from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient

from app.core.database import get_qdrant
from ke.api.routes.schema import _get_db_repo
from ke.api.schemas import (
    KEErrorCode,
    KEResponse,
    error_response,
    success_response,
)
from ke.services.sync import MetadataSyncService
from ke.stores.schema.repository import DatabaseConfigRepository
from ke.stores.vector.repository import VectorRepository
from schema_intelligence.embedding.pipeline import SchemaEmbeddingPipeline
from schema_intelligence.sync.orchestrator import SyncOrchestrator

router = APIRouter(tags=["sync"])


class SyncRequest(BaseModel):
    database_id: str
    password: str | None = None
    run_annotation: bool = True
    run_inference: bool = True


async def _get_metadata_sync_service(
    db_repo: DatabaseConfigRepository = Depends(_get_db_repo),
    qdrant: AsyncQdrantClient = Depends(get_qdrant),
) -> MetadataSyncService:
    vector_repo = VectorRepository(qdrant)
    embedding_pipeline = SchemaEmbeddingPipeline(vector_repository=vector_repo)
    sync_orchestrator = SyncOrchestrator()
    return MetadataSyncService(
        db_repo=db_repo,
        sync_orchestrator=sync_orchestrator,
        embedding_pipeline=embedding_pipeline,
    )


@router.post("/sync", response_model=KEResponse[dict])
async def sync_database(
    request: Request,
    payload: SyncRequest,
    service: MetadataSyncService = Depends(_get_metadata_sync_service),
):
    try:
        result = await service.sync_database(
            database_id=payload.database_id,
            password=payload.password,
            run_annotation=payload.run_annotation,
            run_inference=payload.run_inference,
        )
        return success_response(result)
    except ValueError as e:
        return error_response(
            KEErrorCode.ENTITY_NOT_FOUND,
            {"database_id": payload.database_id, "detail": str(e)},
        )
    except Exception as e:
        return error_response(
            KEErrorCode.STORE_OPERATION_FAILED,
            {"database_id": payload.database_id, "error": str(e)},
        )
