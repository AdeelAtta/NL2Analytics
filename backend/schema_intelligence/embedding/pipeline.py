from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from ke.models.vector import EmbeddingItem, EmbeddingResult, VectorPayload, VectorPoint
from ke.stores.vector.embedding import EmbeddingService
from ke.stores.vector.repository import VectorRepository

from schema_intelligence.annotators.base import AnnotationResult
from schema_intelligence.connectors.base import ExtractedColumn, ExtractedTable
from schema_intelligence.inference.base import InferredRelationship
from schema_intelligence.sync.models import SyncChangeType, SyncResult

logger = logging.getLogger(__name__)


class SchemaEmbeddingPipeline:
    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        vector_repository: VectorRepository | None = None,
    ) -> None:
        self._embedding_service = embedding_service or EmbeddingService()
        self._vector_repository = vector_repository

    async def ensure_collection(self, tenant_id: str) -> None:
        if self._vector_repository is not None:
            await self._vector_repository.ensure_collection(tenant_id)

    async def process_table(
        self,
        table: ExtractedTable,
        annotation: AnnotationResult | None = None,
        relationships: list[InferredRelationship] | None = None,
        tenant_id: str = "default",
    ) -> int:
        items = _build_embedding_items(table, annotation, relationships, tenant_id)
        if not items:
            return 0
        await self.ensure_collection(tenant_id)
        results = await self._embedding_service.embed_batch(items)
        points = _to_vector_points(results, tenant_id)
        if self._vector_repository is not None:
            return await self._vector_repository.upsert_points(tenant_id, points)
        return len(points)

    async def process_batch(
        self,
        tables: list[ExtractedTable],
        annotations: list[AnnotationResult] | None = None,
        relationships: list[InferredRelationship] | None = None,
        tenant_id: str = "default",
    ) -> dict[str, Any]:
        annotation_map: dict[str, AnnotationResult] = {}
        if annotations is not None:
            for a in annotations:
                annotation_map[a.table_name] = a

        all_items: list[EmbeddingItem] = []
        table_points: dict[str, list[VectorPoint]] = {}

        for table in tables:
            ann = annotation_map.get(table.name)
            items = _build_embedding_items(table, ann, relationships, tenant_id)
            all_items.extend(items)

        if not all_items:
            return {"total_points": 0, "tables_processed": 0}

        await self.ensure_collection(tenant_id)
        results = await self._embedding_service.embed_batch(all_items)
        points = _to_vector_points(results, tenant_id)

        if self._vector_repository is not None:
            count = await self._vector_repository.upsert_points(tenant_id, points)
        else:
            count = len(points)

        return {
            "total_points": count,
            "tables_processed": len(tables),
            "items_count": len(all_items),
        }

    async def process_sync_result(
        self,
        result: SyncResult,
        tenant_id: str = "default",
    ) -> dict[str, Any]:
        added_or_changed = [
            c for c in result.changes
            if c.change_type in (SyncChangeType.ADDED, SyncChangeType.CHANGED)
        ]
        removed = [
            c for c in result.changes
            if c.change_type == SyncChangeType.REMOVED
        ]

        upserted = 0
        if added_or_changed:
            tables = [c.table for c in added_or_changed]
            annotations = [c.annotation for c in added_or_changed if c.annotation is not None]
            relationships: list[InferredRelationship] = []
            for c in added_or_changed:
                if c.relationships:
                    relationships.extend(c.relationships)
            upserted = (await self.process_batch(tables, annotations, relationships, tenant_id))["total_points"]

        deleted = 0
        if removed and self._vector_repository is not None:
            for change in removed:
                table_ids = [
                    _point_id(tenant_id, f"table:{change.table.name}"),
                ]
                column_ids = [
                    _point_id(tenant_id, f"column:{change.table.name}.{col.name}")
                    for col in change.table.columns
                ]
                all_ids = table_ids + column_ids
                if all_ids:
                    await self._vector_repository.delete_points(tenant_id, all_ids)
                    deleted += len(all_ids)

        return {
            "upserted": upserted,
            "deleted": deleted,
            "added_changed": len(added_or_changed),
            "removed": len(removed),
        }

    async def delete_table(
        self, table_name: str, tenant_id: str = "default"
    ) -> int:
        if self._vector_repository is None:
            return 0
        table_id = _point_id(tenant_id, f"table:{table_name}")
        await self._vector_repository.delete_points(tenant_id, [table_id])
        return 1


def _build_embedding_items(
    table: ExtractedTable,
    annotation: AnnotationResult | None = None,
    relationships: list[InferredRelationship] | None = None,
    tenant_id: str = "default",
) -> list[EmbeddingItem]:
    items: list[EmbeddingItem] = []
    table_desc = annotation.table_description if annotation else ""
    table_text = f"Table {table.name}"
    if table_desc:
        table_text += f": {table_desc}"
    if table.ddl:
        table_text += f"\nDDL: {table.ddl[:500]}"
    items.append(
        EmbeddingItem(
            id=_point_id(tenant_id, f"table:{table.name}"),
            text=table_text,
            content_type="schema_element",
            source_id=f"schema/{table.name}",
        )
    )
    col_map: dict[str, str] = {}
    if annotation:
        for ac in annotation.columns:
            col_map[ac.name] = ac.description

    for col in table.columns:
        col_desc = col_map.get(col.name, "")
        col_text = f"Column {table.name}.{col.name} ({col.data_type})"
        if col_desc:
            col_text += f": {col_desc}"
        items.append(
            EmbeddingItem(
                id=_point_id(tenant_id, f"column:{table.name}.{col.name}"),
                text=col_text,
                content_type="schema_element",
                source_id=f"schema/{table.name}/{col.name}",
            )
        )

    if relationships:
        for rel in relationships:
            rel_text = f"Relationship: {rel.source_table}.{rel.source_column} -> {rel.target_table}.{rel.target_column} [{rel.strategy}]"
            items.append(
                EmbeddingItem(
                    id=_point_id(tenant_id, f"rel:{rel.source_table}.{rel.source_column}->{rel.target_table}.{rel.target_column}"),
                    text=rel_text,
                    content_type="schema_element",
                    source_id=f"schema/{rel.source_table}/{rel.source_column}->{rel.target_table}",
                )
            )

    return items


def _to_vector_points(
    results: list[EmbeddingResult],
    tenant_id: str,
) -> list[VectorPoint]:
    now = datetime.now(UTC)
    points: list[VectorPoint] = []
    for r in results:
        metadata: dict[str, Any] = {"embedding_id": r.id}
        points.append(
            VectorPoint(
                id=r.id,
                dense_vector=r.dense_vector,
                sparse_vector=r.sparse_vector,
                payload=VectorPayload(
                    tenant_id=tenant_id,
                    content_type="schema_element",
                    source_id=r.id,
                    text="",
                    embedding_model=r.embedding_model,
                    metadata=metadata,
                    created_at=now,
                ),
            )
        )
    return points


def _point_id(tenant_id: str, suffix: str) -> str:
    return f"{tenant_id}:{suffix}"
