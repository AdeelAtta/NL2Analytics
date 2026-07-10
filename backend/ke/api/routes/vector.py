from __future__ import annotations

from fastapi import APIRouter, Depends
from qdrant_client import AsyncQdrantClient

from app.core.database import get_qdrant
from ke.api.schemas import (
    KEListResponse,
    success_response,
)
from ke.models.vector import (
    HybridSearchParams,
    SearchResult,
    VectorPoint,
)
from ke.stores.vector.embedding import EmbeddingService
from ke.stores.vector.repository import VectorRepository

router = APIRouter(tags=["vector"])


async def _get_vector_repo(
    client: AsyncQdrantClient = Depends(get_qdrant),
) -> VectorRepository:
    return VectorRepository(client)


@router.get("/collections", response_model=KEListResponse[str])
async def list_collections(
    tenant_id: str | None = None,
    repo: VectorRepository = Depends(_get_vector_repo),
):
    names = await repo.list_collections(tenant_id=tenant_id)
    return KEListResponse[str](
        data=names,
        meta={"total": len(names)},
    )


@router.post("/collections/ensure")
async def ensure_collection(
    tenant_id: str,
    repo: VectorRepository = Depends(_get_vector_repo),
):
    await repo.ensure_collection(tenant_id)
    return success_response({"tenant_id": tenant_id, "status": "ready"})


@router.get("/collections/{tenant_id}/info")
async def collection_info(
    tenant_id: str,
    repo: VectorRepository = Depends(_get_vector_repo),
):
    info = await repo.collection_info(tenant_id)
    return success_response(info)


@router.delete("/collections/{tenant_id}")
async def delete_collection(
    tenant_id: str,
    repo: VectorRepository = Depends(_get_vector_repo),
):
    await repo.delete_collection(tenant_id)
    return success_response({"tenant_id": tenant_id, "status": "deleted"})


@router.post("/points/upsert")
async def upsert_points(
    tenant_id: str,
    points: list[VectorPoint],
    repo: VectorRepository = Depends(_get_vector_repo),
):
    count = await repo.upsert_points(tenant_id, points)
    return success_response({"upserted": len(points), "status": count})


@router.post("/search", response_model=KEListResponse[SearchResult])
async def search(
    tenant_id: str,
    params: HybridSearchParams,
    repo: VectorRepository = Depends(_get_vector_repo),
    embedder: EmbeddingService = Depends(lambda: EmbeddingService()),
):
    embedding = await embedder.embed_text(params.query)
    if (
        params.dense_weight is not None
        and params.dense_weight < 1.0
        and embedding.sparse_vector is not None
    ):
        results = await repo.search_hybrid(
            tenant_id=tenant_id,
            dense_vector=embedding.dense_vector,
            sparse_vector=embedding.sparse_vector,
            params=params,
        )
    else:
        results = await repo.search(
            tenant_id=tenant_id,
            dense_vector=embedding.dense_vector,
            params=params,
        )
    return KEListResponse[SearchResult](
        data=results,
        meta={"total": len(results)},
    )


@router.delete("/points")
async def delete_points(
    tenant_id: str,
    point_ids: list[str],
    repo: VectorRepository = Depends(_get_vector_repo),
):
    await repo.delete_points(tenant_id, point_ids)
    return success_response({"deleted": len(point_ids)})


@router.get("/count")
async def count_points(
    tenant_id: str,
    content_type: str | None = None,
    repo: VectorRepository = Depends(_get_vector_repo),
):
    count = await repo.count_points(tenant_id, content_type=content_type)
    return success_response({"count": count})
