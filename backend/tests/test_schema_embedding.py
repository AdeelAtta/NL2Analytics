from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from ke.models.vector import EmbeddingResult, SparseVector
from schema_intelligence.annotators.base import AnnotatedColumn, AnnotationResult
from schema_intelligence.connectors.base import (
    ExtractedColumn,
    ExtractedTable,
)
from schema_intelligence.embedding.pipeline import (
    SchemaEmbeddingPipeline,
    _build_embedding_items,
    _point_id,
    _to_vector_points,
)
from schema_intelligence.inference.base import InferredRelationship
from schema_intelligence.sync.models import (
    SyncChange,
    SyncChangeType,
    SyncResult,
)


# ---------------------------------------------------------------------------
# _point_id
# ---------------------------------------------------------------------------

class TestPointId:
    def test_format(self) -> None:
        assert _point_id("t1", "table:users") == "t1:table:users"

    def test_with_tenant(self) -> None:
        assert _point_id("tenant_abc", "column:public.users.id") == "tenant_abc:column:public.users.id"


# ---------------------------------------------------------------------------
# _build_embedding_items
# ---------------------------------------------------------------------------

class TestBuildEmbeddingItems:
    def test_table_without_annotation(self) -> None:
        table = ExtractedTable(
            name="users",
            columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)],
        )
        items = _build_embedding_items(table, tenant_id="default")
        assert len(items) == 2  # table + 1 column
        assert items[0].text.startswith("Table users")
        assert items[1].text.startswith("Column users.id")

    def test_table_with_annotation(self) -> None:
        table = ExtractedTable(
            name="users",
            columns=[ExtractedColumn(name="email", ordinal_position=1, data_type="VARCHAR", is_nullable=True)],
        )
        annotation = AnnotationResult(
            table_name="users",
            table_description="User accounts",
            columns=[AnnotatedColumn(name="email", description="Primary email address")],
        )
        items = _build_embedding_items(table, annotation=annotation, tenant_id="default")
        assert items[0].text == "Table users: User accounts"
        assert "Primary email address" in items[1].text

    def test_table_with_ddl(self) -> None:
        table = ExtractedTable(
            name="users",
            columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)],
            ddl="CREATE TABLE users (id INT)",
        )
        items = _build_embedding_items(table, tenant_id="default")
        assert "DDL:" in items[0].text
        assert "CREATE TABLE" in items[0].text

    def test_table_with_relationships(self) -> None:
        table = ExtractedTable(
            name="orders",
            columns=[ExtractedColumn(name="customer_id", ordinal_position=1, data_type="INT", is_nullable=True)],
        )
        rels = [
            InferredRelationship(
                source_table="orders",
                source_column="customer_id",
                target_table="customers",
                target_column="id",
                confidence=0.7,
                strategy="naming_heuristic",
            ),
        ]
        items = _build_embedding_items(table, relationships=rels, tenant_id="default")
        assert len(items) == 3  # table + 1 column + 1 relationship
        assert "Relationship:" in items[2].text
        assert "orders.customer_id -> customers.id" in items[2].text

    def test_multiple_columns(self) -> None:
        table = ExtractedTable(
            name="users",
            columns=[
                ExtractedColumn(name="id", ordinal_position=1, data_type="SERIAL", is_nullable=False),
                ExtractedColumn(name="name", ordinal_position=2, data_type="VARCHAR", is_nullable=True),
                ExtractedColumn(name="email", ordinal_position=3, data_type="VARCHAR", is_nullable=True),
            ],
        )
        items = _build_embedding_items(table, tenant_id="default")
        assert len(items) == 4  # table + 3 columns

    def test_empty_table_no_columns(self) -> None:
        table = ExtractedTable(name="empty", columns=[])
        items = _build_embedding_items(table, tenant_id="default")
        assert len(items) == 1  # table only

    def test_source_id_format(self) -> None:
        table = ExtractedTable(
            name="users",
            columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)],
        )
        items = _build_embedding_items(table, tenant_id="t1")
        assert items[0].source_id == "schema/users"
        assert items[1].source_id == "schema/users/id"

    def test_content_type_is_schema_element(self) -> None:
        table = ExtractedTable(
            name="users",
            columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)],
        )
        items = _build_embedding_items(table, tenant_id="default")
        for item in items:
            assert item.content_type == "schema_element"

    def test_point_id_includes_tenant(self) -> None:
        table = ExtractedTable(
            name="users",
            columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)],
        )
        items = _build_embedding_items(table, tenant_id="tenant_x")
        assert items[0].id == "tenant_x:table:users"
        assert items[1].id == "tenant_x:column:users.id"

    def test_annotated_column_fallback_to_empty(self) -> None:
        table = ExtractedTable(
            name="logs",
            columns=[ExtractedColumn(name="message", ordinal_position=1, data_type="TEXT", is_nullable=True)],
        )
        annotation = AnnotationResult(
            table_name="logs",
            table_description="",
            columns=[AnnotatedColumn(name="message", description="")],
        )
        items = _build_embedding_items(table, annotation=annotation, tenant_id="default")
        assert items[1].text == "Column logs.message (TEXT)"

    def test_relationship_ids_are_unique(self) -> None:
        table = ExtractedTable(name="t", columns=[ExtractedColumn(name="a", ordinal_position=1, data_type="INT", is_nullable=True)])
        rels = [
            InferredRelationship(source_table="t", source_column="a", target_table="u", target_column="id"),
            InferredRelationship(source_table="t", source_column="a", target_table="v", target_column="id"),
        ]
        items = _build_embedding_items(table, relationships=rels, tenant_id="default")
        rel_ids = [it.id for it in items if "rel:" in it.id]
        assert len(rel_ids) == 2
        assert rel_ids[0] != rel_ids[1]


# ---------------------------------------------------------------------------
# _to_vector_points
# ---------------------------------------------------------------------------

class TestToVectorPoints:
    def test_single_result(self) -> None:
        results = [
            EmbeddingResult(
                id="t1:table:users",
                dense_vector=[0.1, 0.2, 0.3],
                sparse_vector=SparseVector(indices=[1, 2], values=[0.5, 0.3]),
            ),
        ]
        points = _to_vector_points(results, tenant_id="t1")
        assert len(points) == 1
        assert points[0].id == "t1:table:users"
        assert points[0].dense_vector == [0.1, 0.2, 0.3]
        assert points[0].sparse_vector is not None
        assert points[0].sparse_vector.indices == [1, 2]
        assert points[0].payload.tenant_id == "t1"
        assert points[0].payload.content_type == "schema_element"

    def test_multiple_results(self) -> None:
        results = [
            EmbeddingResult(id="a", dense_vector=[0.1]),
            EmbeddingResult(id="b", dense_vector=[0.2]),
        ]
        points = _to_vector_points(results, tenant_id="default")
        assert len(points) == 2

    def test_created_at_is_set(self) -> None:
        results = [EmbeddingResult(id="x", dense_vector=[0.5])]
        points = _to_vector_points(results, tenant_id="t")
        assert isinstance(points[0].payload.created_at, datetime)
        assert points[0].payload.created_at.tzinfo is not None

    def test_empty_results(self) -> None:
        points = _to_vector_points([], tenant_id="t")
        assert points == []

    def test_payload_has_metadata(self) -> None:
        results = [EmbeddingResult(id="x", dense_vector=[0.5])]
        points = _to_vector_points(results, tenant_id="t")
        assert "embedding_id" in points[0].payload.metadata
        assert points[0].payload.metadata["embedding_id"] == "x"

    def test_sparse_vector_none(self) -> None:
        results = [EmbeddingResult(id="x", dense_vector=[0.5], sparse_vector=None)]
        points = _to_vector_points(results, tenant_id="t")
        assert points[0].sparse_vector is None


# ---------------------------------------------------------------------------
# SchemaEmbeddingPipeline
# ---------------------------------------------------------------------------

class TestSchemaEmbeddingPipeline:
    def test_init_defaults(self) -> None:
        pipeline = SchemaEmbeddingPipeline()
        assert pipeline._embedding_service is not None
        assert pipeline._vector_repository is None

    def test_init_with_repository(self) -> None:
        mock_repo = MagicMock()
        pipeline = SchemaEmbeddingPipeline(vector_repository=mock_repo)
        assert pipeline._vector_repository is mock_repo

    async def test_process_table_no_repository(self) -> None:
        pipeline = SchemaEmbeddingPipeline()
        table = ExtractedTable(
            name="users",
            columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)],
        )
        count = await pipeline.process_table(table, tenant_id="default")
        assert count == 2  # table + 1 column

    async def test_process_table_with_empty_columns(self) -> None:
        pipeline = SchemaEmbeddingPipeline()
        table = ExtractedTable(name="empty", columns=[])
        count = await pipeline.process_table(table, tenant_id="default")
        assert count == 1  # table only

    async def test_process_table_with_annotation(self) -> None:
        pipeline = SchemaEmbeddingPipeline()
        table = ExtractedTable(
            name="users",
            columns=[ExtractedColumn(name="email", ordinal_position=1, data_type="VARCHAR", is_nullable=True)],
        )
        annotation = AnnotationResult(
            table_name="users",
            table_description="Stores user accounts",
            columns=[AnnotatedColumn(name="email", description="Email address")],
        )
        count = await pipeline.process_table(table, annotation=annotation, tenant_id="default")
        assert count == 2

    async def test_process_table_with_relationships(self) -> None:
        pipeline = SchemaEmbeddingPipeline()
        table = ExtractedTable(
            name="orders",
            columns=[ExtractedColumn(name="customer_id", ordinal_position=1, data_type="INT", is_nullable=True)],
        )
        rels = [
            InferredRelationship(
                source_table="orders", source_column="customer_id",
                target_table="customers", target_column="id",
            ),
        ]
        count = await pipeline.process_table(table, relationships=rels, tenant_id="default")
        assert count == 3  # table + 1 column + 1 relationship

    async def test_process_table_upserts_to_repository(self) -> None:
        mock_repo = AsyncMock()
        mock_repo.upsert_points.return_value = 3
        pipeline = SchemaEmbeddingPipeline(vector_repository=mock_repo)
        table = ExtractedTable(
            name="users",
            columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)],
        )
        count = await pipeline.process_table(table, tenant_id="t1")
        assert count == 3
        mock_repo.ensure_collection.assert_awaited_once_with("t1")
        mock_repo.upsert_points.assert_awaited_once()

    async def test_process_batch_multiple_tables(self) -> None:
        pipeline = SchemaEmbeddingPipeline()
        tables = [
            ExtractedTable(name="a", columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)]),
            ExtractedTable(name="b", columns=[ExtractedColumn(name="val", ordinal_position=1, data_type="TEXT", is_nullable=True)]),
        ]
        result = await pipeline.process_batch(tables, tenant_id="default")
        assert result["tables_processed"] == 2
        assert result["total_points"] == 4  # 2 tables + 2 columns

    async def test_process_batch_empty_tables(self) -> None:
        pipeline = SchemaEmbeddingPipeline()
        result = await pipeline.process_batch([], tenant_id="default")
        assert result["total_points"] == 0
        assert result["tables_processed"] == 0

    async def test_process_batch_upserts_to_repository(self) -> None:
        mock_repo = AsyncMock()
        mock_repo.upsert_points.return_value = 2
        pipeline = SchemaEmbeddingPipeline(vector_repository=mock_repo)
        tables = [
            ExtractedTable(name="x", columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)]),
        ]
        result = await pipeline.process_batch(tables, tenant_id="t1")
        assert result["total_points"] == 2
        mock_repo.ensure_collection.assert_awaited_once_with("t1")

    async def test_process_sync_result_added_only(self) -> None:
        pipeline = SchemaEmbeddingPipeline()
        table = ExtractedTable(
            name="users",
            columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)],
        )
        result = SyncResult(
            schema_info=MagicMock(),
            changes=[
                SyncChange(table=table, change_type=SyncChangeType.ADDED),
            ],
        )
        stats = await pipeline.process_sync_result(result, tenant_id="default")
        assert stats["added_changed"] == 1
        assert stats["removed"] == 0
        assert stats["upserted"] > 0

    async def test_process_sync_result_removed_only(self) -> None:
        mock_repo = AsyncMock()
        pipeline = SchemaEmbeddingPipeline(vector_repository=mock_repo)
        table = ExtractedTable(
            name="old_table",
            columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)],
        )
        result = SyncResult(
            schema_info=MagicMock(),
            changes=[
                SyncChange(table=table, change_type=SyncChangeType.REMOVED),
            ],
        )
        stats = await pipeline.process_sync_result(result, tenant_id="t1")
        assert stats["removed"] == 1
        assert stats["added_changed"] == 0
        mock_repo.delete_points.assert_awaited_once()

    async def test_process_sync_result_mixed(self) -> None:
        mock_repo = AsyncMock()
        mock_repo.upsert_points.return_value = 4
        pipeline = SchemaEmbeddingPipeline(vector_repository=mock_repo)
        t1 = ExtractedTable(name="keep", columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)])
        t2 = ExtractedTable(name="gone", columns=[ExtractedColumn(name="x", ordinal_position=1, data_type="INT", is_nullable=False)])
        result = SyncResult(
            schema_info=MagicMock(),
            changes=[
                SyncChange(table=t1, change_type=SyncChangeType.UNCHANGED),
                SyncChange(table=t2, change_type=SyncChangeType.REMOVED),
            ],
        )
        stats = await pipeline.process_sync_result(result, tenant_id="default")
        assert stats["added_changed"] == 0
        assert stats["removed"] == 1

    async def test_process_sync_result_empty(self) -> None:
        pipeline = SchemaEmbeddingPipeline()
        result = SyncResult(
            schema_info=MagicMock(),
            changes=[],
        )
        stats = await pipeline.process_sync_result(result, tenant_id="default")
        assert stats["added_changed"] == 0
        assert stats["upserted"] == 0
        assert stats["removed"] == 0

    async def test_process_sync_result_changed_triggers_upsert(self) -> None:
        pipeline = SchemaEmbeddingPipeline()
        t1 = ExtractedTable(name="evolving", columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)])
        result = SyncResult(
            schema_info=MagicMock(),
            changes=[
                SyncChange(table=t1, change_type=SyncChangeType.CHANGED),
            ],
        )
        stats = await pipeline.process_sync_result(result, tenant_id="default")
        assert stats["added_changed"] == 1
        assert stats["upserted"] > 0

    async def test_ensure_collection_no_repository(self) -> None:
        pipeline = SchemaEmbeddingPipeline()
        await pipeline.ensure_collection("default")

    async def test_ensure_collection_with_repository(self) -> None:
        mock_repo = AsyncMock()
        pipeline = SchemaEmbeddingPipeline(vector_repository=mock_repo)
        await pipeline.ensure_collection("t1")
        mock_repo.ensure_collection.assert_awaited_once_with("t1")

    async def test_delete_table_no_repository(self) -> None:
        pipeline = SchemaEmbeddingPipeline()
        count = await pipeline.delete_table("users", tenant_id="default")
        assert count == 0

    async def test_delete_table_with_repository(self) -> None:
        mock_repo = AsyncMock()
        pipeline = SchemaEmbeddingPipeline(vector_repository=mock_repo)
        count = await pipeline.delete_table("users", tenant_id="t1")
        assert count == 1
        mock_repo.delete_points.assert_awaited_once_with("t1", ["t1:table:users"])

    async def test_process_sync_result_with_annotations_and_rels(self) -> None:
        pipeline = SchemaEmbeddingPipeline()
        table = ExtractedTable(
            name="orders",
            columns=[ExtractedColumn(name="customer_id", ordinal_position=1, data_type="INT", is_nullable=True)],
        )
        annotation = AnnotationResult(
            table_name="orders",
            table_description="Order records",
            columns=[AnnotatedColumn(name="customer_id", description="FK to customers")],
        )
        rels = [
            InferredRelationship(
                source_table="orders", source_column="customer_id",
                target_table="customers", target_column="id",
                strategy="naming_heuristic",
            ),
        ]
        result = SyncResult(
            schema_info=MagicMock(),
            changes=[
                SyncChange(
                    table=table,
                    change_type=SyncChangeType.ADDED,
                    annotation=annotation,
                    relationships=rels,
                ),
            ],
        )
        stats = await pipeline.process_sync_result(result, tenant_id="default")
        assert stats["added_changed"] == 1
        assert stats["upserted"] > 0
