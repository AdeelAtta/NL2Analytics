from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qdrant_models

from ke.models.vector import (
    HybridSearchParams,
    SearchResult,
    SparseVector,
    VectorPayload,
    VectorPoint,
)

_CONTENT_TYPES = frozenset({"schema_element", "query_pattern", "business_term"})


def _tenant_collection_name(tenant_id: str) -> str:
    return f"tenant_{tenant_id}_embeddings"


def _point_to_search_result(
    point: qdrant_models.ScoredPoint,
) -> SearchResult:
    payload = point.payload or {}
    raw_type = str(payload.get("content_type", "schema_element"))
    content_type = raw_type if raw_type in _CONTENT_TYPES else "schema_element"
    return SearchResult(
        id=str(point.id),
        score=point.score,
        payload=VectorPayload(
            tenant_id=str(payload.get("tenant_id", "")),
            content_type=content_type,  # type: ignore[arg-type]
            source_id=str(payload.get("source_id", "")),
            text=str(payload.get("text", "")),
            embedding_model=str(payload.get("embedding_model", "BAAI/bge-m3")),
            metadata=dict(payload.get("metadata", {})),
            created_at=(
                datetime.fromisoformat(payload["created_at"])
                if "created_at" in payload else datetime.now(UTC)
            ),
        ),
        dense_score=point.score if point.version is not None else None,
        sparse_score=None,
    )


class VectorRepository:
    def __init__(self, client: AsyncQdrantClient) -> None:
        self._client = client

    async def ensure_collection(
        self,
        tenant_id: str,
        vectors_config: qdrant_models.VectorsConfig | None = None,
    ) -> None:
        collection_name = _tenant_collection_name(tenant_id)
        result = await self._client.get_collections()
        existing = {c.name for c in result.collections}
        if collection_name in existing:
            return
        await self._client.create_collection(
            collection_name=collection_name,
            vectors_config=vectors_config or qdrant_models.VectorParams(
                size=1024, distance=qdrant_models.Distance.COSINE
            ),
            sparse_vectors_config={
                "sparse": qdrant_models.SparseVectorParams(
                    index=qdrant_models.SparseIndexParams(
                        full_scan_threshold=20000,
                    ),
                ),
            },
        )

    async def upsert_points(
        self, tenant_id: str, points: list[VectorPoint]
    ) -> int:
        collection_name = _tenant_collection_name(tenant_id)
        qdrant_points: list[qdrant_models.PointStruct] = []
        for p in points:
            vectors: dict[str, Any] = {
                "dense": p.dense_vector,
            }
            if p.sparse_vector is not None:
                vectors["sparse"] = qdrant_models.SparseVector(
                    indices=p.sparse_vector.indices,
                    values=p.sparse_vector.values,
                )
            qdrant_points.append(
                qdrant_models.PointStruct(
                    id=p.id,
                    vector=vectors,
                    payload={
                        "tenant_id": p.payload.tenant_id,
                        "content_type": p.payload.content_type,
                        "source_id": p.payload.source_id,
                        "text": p.payload.text,
                        "embedding_model": p.payload.embedding_model,
                        "metadata": p.payload.metadata,
                        "created_at": p.payload.created_at.isoformat(),
                    },
                )
            )
        result = await self._client.upsert(
            collection_name=collection_name,
            points=qdrant_points,
        )
        return int(result.status)

    async def search(
        self,
        tenant_id: str,
        dense_vector: list[float],
        sparse_vector: SparseVector | None = None,
        params: HybridSearchParams | None = None,
    ) -> list[SearchResult]:
        collection_name = _tenant_collection_name(tenant_id)
        query_filter = _build_filter(params) if params else None
        search_params = qdrant_models.SearchParams(
            exact=False,
            hnsw_ef=128,
        )
        response = await self._client.query_points(
            collection_name=collection_name,
            query=dense_vector,
            using="dense",
            query_filter=query_filter,
            limit=params.limit if params else 20,
            offset=params.offset if params else 0,
            score_threshold=params.score_threshold if params and params.score_threshold else None,
            search_params=search_params,
        )
        return [_point_to_search_result(p) for p in response.points]

    async def search_hybrid(
        self,
        tenant_id: str,
        dense_vector: list[float],
        sparse_vector: SparseVector | None = None,
        params: HybridSearchParams | None = None,
    ) -> list[SearchResult]:
        if sparse_vector is None:
            return await self.search(tenant_id, dense_vector, None, params)

        collection_name = _tenant_collection_name(tenant_id)
        query_filter = _build_filter(params) if params else None

        prefetch = qdrant_models.Prefetch(
            query=dense_vector,
            using="dense",
            limit=params.limit * 3 if params else 60,
        )
        dense_weight = params.dense_weight if params else 0.7
        sparse_weight = 1.0 - dense_weight
        response = await self._client.query_points(
            collection_name=collection_name,
            query=qdrant_models.SparseVector(
                indices=sparse_vector.indices,
                values=[v * sparse_weight for v in sparse_vector.values],
            ),
            using="sparse",
            query_filter=query_filter,
            prefetch=prefetch,
            limit=params.limit if params else 20,
            offset=params.offset if params else 0,
            score_threshold=params.score_threshold if params and params.score_threshold else None,
        )
        return [_point_to_search_result(p) for p in response.points]

    async def delete_points(
        self, tenant_id: str, point_ids: list[str]
    ) -> None:
        collection_name = _tenant_collection_name(tenant_id)
        await self._client.delete(
            collection_name=collection_name,
            points_selector=qdrant_models.PointIdsList(
                points=[str(pid) for pid in point_ids],
            ),
        )

    async def delete_by_filter(
        self, tenant_id: str, content_type: str | None = None, source_id: str | None = None
    ) -> None:
        collection_name = _tenant_collection_name(tenant_id)
        conditions: list[qdrant_models.FieldCondition] = []
        if content_type:
            conditions.append(
                qdrant_models.FieldCondition(
                    key="content_type",
                    match=qdrant_models.MatchValue(value=content_type),
                )
            )
        if source_id:
            conditions.append(
                qdrant_models.FieldCondition(
                    key="source_id",
                    match=qdrant_models.MatchValue(value=source_id),
                )
            )
        if conditions:
            await self._client.delete(
                collection_name=collection_name,
                points_selector=qdrant_models.FilterSelector(
                    filter=qdrant_models.Filter(must=conditions),  # type: ignore[arg-type]
                ),
            )

    async def count_points(
        self, tenant_id: str, content_type: str | None = None
    ) -> int:
        collection_name = _tenant_collection_name(tenant_id)
        query_filter = None
        if content_type:
            query_filter = qdrant_models.Filter(
                must=[
                    qdrant_models.FieldCondition(
                        key="content_type",
                        match=qdrant_models.MatchValue(value=content_type),
                    )
                ]
            )
        result = await self._client.count(
            collection_name=collection_name,
            count_filter=query_filter,
            exact=True,
        )
        return result.count

    async def list_collections(self, tenant_id: str | None = None) -> list[str]:
        collections = await self._client.get_collections()
        names = [c.name for c in collections.collections]
        if tenant_id:
            prefix = _tenant_collection_name(tenant_id)
            return [n for n in names if n == prefix]
        return names

    async def delete_collection(self, tenant_id: str) -> None:
        collection_name = _tenant_collection_name(tenant_id)
        await self._client.delete_collection(collection_name=collection_name)

    async def collection_info(self, tenant_id: str) -> dict[str, Any]:
        collection_name = _tenant_collection_name(tenant_id)
        info = await self._client.get_collection(collection_name=collection_name)
        return {
            "name": collection_name,
            "status": str(info.status),
            "vectors_count": info.indexed_vectors_count,
            "points_count": info.points_count,
            "segments_count": info.segments_count,
        }


def _build_filter(params: HybridSearchParams) -> qdrant_models.Filter:
    conditions: list[qdrant_models.FieldCondition] = []
    if params.content_type:
        conditions.append(
            qdrant_models.FieldCondition(
                key="content_type",
                match=qdrant_models.MatchValue(value=params.content_type),
            )
        )
    if params.tenant_id:
        conditions.append(
            qdrant_models.FieldCondition(
                key="tenant_id",
                match=qdrant_models.MatchValue(value=params.tenant_id),
            )
        )
    return qdrant_models.Filter(must=conditions)  # type: ignore[arg-type]
