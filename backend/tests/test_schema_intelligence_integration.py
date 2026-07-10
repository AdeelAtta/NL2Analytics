from __future__ import annotations

import os
import tempfile
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import duckdb
import pytest

from ke.models.vector import EmbeddingResult

from schema_intelligence.annotators.base import (
    AnnotatedColumn,
    AnnotationResult,
    BaseAnnotator,
)
from schema_intelligence.annotators.rule_based import RuleBasedAnnotator
from schema_intelligence.connectors.base import (
    ConnectorConfig,
    ConnectorRegistry,
    ExtractedColumn,
    ExtractedTable,
)
from schema_intelligence.connectors.duckdb import DuckDBConnector
from schema_intelligence.embedding.pipeline import (
    SchemaEmbeddingPipeline,
    _build_embedding_items,
    _point_id,
    _to_vector_points,
)
from schema_intelligence.inference.base import InferredRelationship
from schema_intelligence.inference.engine import RelationshipInferenceService
from schema_intelligence.sync.models import (
    SyncChange,
    SyncChangeType,
    SyncResult,
    SyncState,
    table_signature,
)
from schema_intelligence.sync.orchestrator import SyncOrchestrator


def _create_db(path: str) -> None:
    if os.path.exists(path):
        os.remove(path)
    conn = duckdb.connect(path)
    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            total DECIMAL(10,2) NOT NULL DEFAULT 0.00,
            status VARCHAR(20) DEFAULT 'pending',
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            category VARCHAR(50)
        )
    """)
    conn.execute("""
        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            unit_price DECIMAL(10,2) NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)
    conn.close()


@pytest.fixture(scope="session")
def register_duckdb() -> None:
    try:
        ConnectorRegistry.get_connector("duckdb")
    except KeyError:
        ConnectorRegistry.register("duckdb", DuckDBConnector)


@pytest.fixture
def empty_db_path() -> str:
    path = os.path.join(tempfile.gettempdir(), f"test_empty_{uuid.uuid4().hex}.db")
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def populated_db_path() -> str:
    path = os.path.join(tempfile.gettempdir(), f"test_pop_{uuid.uuid4().hex}.db")
    _create_db(path)
    yield path
    if os.path.exists(path):
        os.unlink(path)


# ---------------------------------------------------------------------------
# DuckDB full integration tests
# ---------------------------------------------------------------------------

class TestDuckDBIntegration:
    async def test_connect_and_extract_schemas(self, empty_db_path: str) -> None:
        config = ConnectorConfig(
            host="localhost", port=0, database=empty_db_path,
            username="", password="",
        )
        connector = DuckDBConnector()
        await connector.connect(config)
        try:
            schemas = await connector.extract_schemas()
            assert len(schemas) >= 1
            schema_names = [s.name for s in schemas]
            assert "main" in schema_names
        finally:
            await connector.close()

    async def test_extract_tables(self, populated_db_path: str) -> None:
        config = ConnectorConfig(
            host="localhost", port=0, database=populated_db_path,
            username="", password="",
        )
        connector = DuckDBConnector()
        await connector.connect(config)
        try:
            tables = await connector.extract_tables("main")
            table_names = {t.name for t in tables}
            assert "users" in table_names
            assert "orders" in table_names
            assert "products" in table_names
            assert "order_items" in table_names
        finally:
            await connector.close()

    async def test_extract_columns_with_types(self, populated_db_path: str) -> None:
        config = ConnectorConfig(
            host="localhost", port=0, database=populated_db_path,
            username="", password="",
        )
        connector = DuckDBConnector()
        await connector.connect(config)
        try:
            cols = await connector.extract_columns("main", "users")
            col_map = {c.name: c for c in cols}
            assert col_map["id"].is_primary_key is True
            assert col_map["id"].is_nullable is False
            assert col_map["name"].is_nullable is False
            assert col_map["name"].data_type == "VARCHAR"
            assert col_map["email"].is_nullable is True
            assert "CURRENT_TIMESTAMP" in (col_map["created_at"].default_value or "")

            order_cols = await connector.extract_columns("main", "orders")
            order_map = {c.name: c for c in order_cols}
            assert order_map["user_id"].foreign_key is not None
            assert order_map["user_id"].foreign_key.ref_table == "users"
            assert order_map["user_id"].foreign_key.ref_column == "id"
        finally:
            await connector.close()

    async def test_extract_relationships(self, populated_db_path: str) -> None:
        config = ConnectorConfig(
            host="localhost", port=0, database=populated_db_path,
            username="", password="",
        )
        connector = DuckDBConnector()
        await connector.connect(config)
        try:
            rels = await connector.extract_relationships()
            rel_key = {(r["table"], r["column"], r["ref_table"]): r for r in rels}
            assert ("orders", "user_id", "users") in rel_key
            assert ("order_items", "order_id", "orders") in rel_key
            assert ("order_items", "product_id", "products") in rel_key
        finally:
            await connector.close()

    async def test_full_sync_detects_additions(
        self, populated_db_path: str, register_duckdb: None
    ) -> None:
        config = ConnectorConfig(
            host="localhost", port=0, database=populated_db_path,
            username="", password="",
        )
        orch = SyncOrchestrator()
        result = await orch.sync(
            config, db_type="duckdb",
            run_annotation=True, run_inference=True,
        )
        assert result.added_count == 4
        assert result.removed_count == 0
        assert result.unchanged_count == 0

    async def test_full_sync_with_annotation(
        self, populated_db_path: str, register_duckdb: None
    ) -> None:
        config = ConnectorConfig(
            host="localhost", port=0, database=populated_db_path,
            username="", password="",
        )
        orch = SyncOrchestrator()
        result = await orch.sync(
            config, db_type="duckdb",
            run_annotation=True, run_inference=False,
        )
        added = [c for c in result.changes if c.change_type == SyncChangeType.ADDED]
        for change in added:
            assert change.annotation is not None
            assert change.annotation.table_name in ("users", "orders", "products", "order_items")

    async def test_full_sync_has_existing_fk_columns(
        self, populated_db_path: str, register_duckdb: None
    ) -> None:
        config = ConnectorConfig(
            host="localhost", port=0, database=populated_db_path,
            username="", password="",
        )
        orch = SyncOrchestrator()
        result = await orch.sync(
            config, db_type="duckdb",
            run_annotation=False, run_inference=False,
        )
        added = [c for c in result.changes if c.change_type == SyncChangeType.ADDED]
        added_tables = {c.table.name for c in added}
        assert "orders" in added_tables
        orders_table = next(c.table for c in added if c.table.name == "orders")
        user_id_col = next(c for c in orders_table.columns if c.name == "user_id")
        assert user_id_col.foreign_key is not None
        assert user_id_col.foreign_key.ref_table == "users"
        assert user_id_col.foreign_key.ref_column == "id"

    async def test_inference_on_tables_without_declared_fks(
        self, register_duckdb: None
    ) -> None:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        if os.path.exists(path):
            os.remove(path)
        conn = duckdb.connect(path)
        conn.execute("CREATE TABLE customers (id INT PRIMARY KEY, name VARCHAR(100))")
        conn.execute("""CREATE TABLE orders (
            id INT PRIMARY KEY,
            customer_id INT NOT NULL,
            total DECIMAL(10,2)
        )""")
        conn.close()

        config = ConnectorConfig(
            host="localhost", port=0, database=path,
            username="", password="",
        )
        orch = SyncOrchestrator()
        result = await orch.sync(
            config, db_type="duckdb",
            run_annotation=False, run_inference=True,
        )
        added = [c for c in result.changes if c.change_type == SyncChangeType.ADDED]
        has_rels = any(
            c.relationships is not None and len(c.relationships) > 0
            for c in added
        )
        assert has_rels
        if os.path.exists(path):
            os.unlink(path)

    async def test_incremental_sync_no_changes(
        self, populated_db_path: str, register_duckdb: None
    ) -> None:
        config = ConnectorConfig(
            host="localhost", port=0, database=populated_db_path,
            username="", password="",
        )
        orch = SyncOrchestrator()
        await orch.sync(config, db_type="duckdb", run_annotation=False, run_inference=False)
        result2 = await orch.sync(config, db_type="duckdb", run_annotation=False, run_inference=False)
        assert result2.unchanged_count == 4
        assert result2.added_count == 0
        assert result2.changed_count == 0

    async def test_sync_empty_database(
        self, empty_db_path: str, register_duckdb: None
    ) -> None:
        config = ConnectorConfig(
            host="localhost", port=0, database=empty_db_path,
            username="", password="",
        )
        orch = SyncOrchestrator()
        result = await orch.sync(
            config, db_type="duckdb",
            run_annotation=False, run_inference=False,
        )
        assert result.added_count == 0
        assert len(result.changes) == 0

    async def test_sync_with_schema_filter(
        self, populated_db_path: str, register_duckdb: None
    ) -> None:
        config = ConnectorConfig(
            host="localhost", port=0, database=populated_db_path,
            username="", password="", schema_filter=["main"],
        )
        orch = SyncOrchestrator()
        result = await orch.sync(
            config, db_type="duckdb",
            schemas=["main"],
            run_annotation=False, run_inference=False,
        )
        assert result.added_count == 4

    async def test_sync_with_ddl_override(
        self, populated_db_path: str, register_duckdb: None
    ) -> None:
        from schema_intelligence.parsers.ddl_parser import DDLParser

        ddl = "CREATE TABLE custom (id INT PRIMARY KEY, val VARCHAR(50));"
        orch = SyncOrchestrator(ddl_parser=DDLParser())
        config = ConnectorConfig(
            host="localhost", port=0, database=populated_db_path,
            username="", password="",
        )
        result = await orch.sync(
            config, db_type="duckdb",
            run_annotation=False, run_inference=False,
            ddl_override=ddl,
        )
        assert result.added_count == 1
        assert result.schema_info.tables[0].name == "custom"

    async def test_sync_round_trip_change_signature(
        self, populated_db_path: str, register_duckdb: None
    ) -> None:
        config = ConnectorConfig(
            host="localhost", port=0, database=populated_db_path,
            username="", password="",
        )
        orch = SyncOrchestrator()
        result = await orch.sync(config, db_type="duckdb", run_annotation=False, run_inference=False)
        for change in result.changes:
            if change.change_type == SyncChangeType.ADDED:
                assert change.current_signature is not None

    async def test_connector_not_found_error(
        self, empty_db_path: str, register_duckdb: None
    ) -> None:
        config = ConnectorConfig(
            host="localhost", port=0, database=empty_db_path,
            username="", password="",
        )
        orch = SyncOrchestrator()
        with pytest.raises(KeyError):
            await orch.sync(config, db_type="nonexistent")

    async def test_connect_error(self, register_duckdb: None) -> None:
        config = ConnectorConfig(
            host="localhost", port=0,
            database="C:\\nonexistent\\path\\db.db",
            username="", password="",
        )
        orch = SyncOrchestrator()
        with pytest.raises(ConnectionError):
            await orch.sync(config, db_type="duckdb")


# ---------------------------------------------------------------------------
# Annotation + Inference integration
# ---------------------------------------------------------------------------

class TestAnnotationInferenceIntegration:
    async def test_rule_based_annotates_table(self) -> None:
        annotator = RuleBasedAnnotator()
        table = ExtractedTable(
            name="users",
            columns=[
                ExtractedColumn(name="id", ordinal_position=1, data_type="INTEGER", is_nullable=False, is_primary_key=True),
                ExtractedColumn(name="email", ordinal_position=2, data_type="VARCHAR", is_nullable=True),
            ],
        )
        result = await annotator.annotate(table)
        assert result.table_name == "users"
        assert len(result.columns) == 2

    async def test_rule_based_annotates_id_column(self) -> None:
        annotator = RuleBasedAnnotator()
        table = ExtractedTable(
            name="users",
            columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INTEGER", is_nullable=False, is_primary_key=True)],
        )
        result = await annotator.annotate(table)
        assert "identifier" in result.columns[0].description.lower()

    def test_inference_finds_foreign_key_patterns(self) -> None:
        service = RelationshipInferenceService()
        tables = [
            ExtractedTable(
                name="users",
                columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INTEGER", is_nullable=False, is_primary_key=True)],
            ),
            ExtractedTable(
                name="orders",
                columns=[
                    ExtractedColumn(name="id", ordinal_position=1, data_type="INTEGER", is_nullable=False, is_primary_key=True),
                    ExtractedColumn(name="user_id", ordinal_position=2, data_type="INTEGER", is_nullable=True),
                ],
            ),
        ]
        rels = service.infer(tables)
        user_id_rels = [r for r in rels if r.source_column == "user_id"]
        assert len(user_id_rels) >= 1
        assert user_id_rels[0].target_table == "users"

    def test_inference_no_false_positives(self) -> None:
        service = RelationshipInferenceService(min_confidence=0.8)
        tables = [
            ExtractedTable(
                name="a",
                columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INTEGER", is_nullable=False, is_primary_key=True)],
            ),
            ExtractedTable(
                name="b",
                columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INTEGER", is_nullable=False, is_primary_key=True)],
            ),
        ]
        rels = service.infer(tables)
        assert len(rels) == 0


# ---------------------------------------------------------------------------
# Embedding pipeline integration
# ---------------------------------------------------------------------------

class TestEmbeddingPipelineIntegration:
    def test_build_embedding_items_from_table(self) -> None:
        table = ExtractedTable(
            name="users",
            columns=[
                ExtractedColumn(name="id", ordinal_position=1, data_type="INTEGER", is_nullable=False, is_primary_key=True),
                ExtractedColumn(name="email", ordinal_position=2, data_type="VARCHAR(255)", is_nullable=True),
            ],
        )
        annotation = AnnotationResult(
            table_name="users",
            table_description="User accounts",
            columns=[
                AnnotatedColumn(name="id", description="Primary key identifier"),
                AnnotatedColumn(name="email", description="Email address"),
            ],
        )
        items = _build_embedding_items(table, annotation, [], "tenant1")
        assert len(items) == 3  # table + 2 columns
        item_ids = {i.id for i in items}
        assert f"{_point_id('tenant1', 'table:users')}" in item_ids
        assert f"{_point_id('tenant1', 'column:users.id')}" in item_ids
        assert f"{_point_id('tenant1', 'column:users.email')}" in item_ids

    def test_build_embedding_items_with_relationships(self) -> None:
        table = ExtractedTable(
            name="orders",
            columns=[ExtractedColumn(name="user_id", ordinal_position=1, data_type="INTEGER", is_nullable=True)],
        )
        rels = [
            InferredRelationship(
                source_table="orders",
                source_column="user_id",
                target_table="users",
                target_column="id",
                strategy="foreign_key",
                confidence=0.95,
            ),
        ]
        items = _build_embedding_items(table, relationships=rels, tenant_id="t1")
        # table item + column item + relationship item
        assert len(items) == 3
        rel_ids = [i.id for i in items if "rel:" in i.id]
        assert len(rel_ids) == 1
        expected_id = _point_id("t1", "rel:orders.user_id->users.id")
        assert expected_id in rel_ids

    def test_to_vector_points_from_results(self) -> None:
        results = [
            EmbeddingResult(
                id="t1:table:users",
                dense_vector=[0.1, 0.2, 0.3],
                sparse_vector=None,
            ),
        ]
        points = _to_vector_points(results, "t1")
        assert len(points) == 1
        assert points[0].id == "t1:table:users"


# ---------------------------------------------------------------------------
# Cross-component error handling
# ---------------------------------------------------------------------------

class TestErrorHandlingIntegration:
    async def test_orchestrator_recovers_from_partial_failure(
        self, populated_db_path: str, register_duckdb: None
    ) -> None:
        config = ConnectorConfig(
            host="localhost", port=0, database=populated_db_path,
            username="", password="",
        )
        orch = SyncOrchestrator()
        result = await orch.sync(
            config, db_type="duckdb",
            run_annotation=True, run_inference=True,
        )
        assert result.added_count == 4
        assert result.errors == []

    async def test_consecutive_syncs_preserve_state(
        self, populated_db_path: str, register_duckdb: None
    ) -> None:
        config = ConnectorConfig(
            host="localhost", port=0, database=populated_db_path,
            username="", password="",
        )
        orch = SyncOrchestrator()
        r1 = await orch.sync(config, db_type="duckdb", run_annotation=False, run_inference=False)
        assert r1.added_count == 4

        r2 = await orch.sync(config, db_type="duckdb", run_annotation=False, run_inference=False)
        assert r2.unchanged_count == 4

        r3 = await orch.sync(config, db_type="duckdb", run_annotation=False, run_inference=False)
        assert r3.unchanged_count == 4

    async def test_sync_close_then_reopen(
        self, populated_db_path: str, register_duckdb: None
    ) -> None:
        class TrackConnector(DuckDBConnector):
            opens = 0
            closes = 0

            async def connect(self, config: ConnectorConfig) -> None:
                await super().connect(config)
                TrackConnector.opens += 1

            async def close(self) -> None:
                await super().close()
                TrackConnector.closes += 1

        orig = ConnectorRegistry._connectors["duckdb"]
        ConnectorRegistry.register("duckdb", TrackConnector)
        try:
            config = ConnectorConfig(
                host="localhost", port=0, database=populated_db_path,
                username="", password="",
            )
            orch = SyncOrchestrator()
            await orch.sync(config, db_type="duckdb", run_annotation=False, run_inference=False)
            assert TrackConnector.opens == 1
            assert TrackConnector.closes == 1

            await orch.sync(config, db_type="duckdb", run_annotation=False, run_inference=False)
            assert TrackConnector.opens == 2
            assert TrackConnector.closes == 2
        finally:
            ConnectorRegistry._connectors["duckdb"] = orig


# ---------------------------------------------------------------------------
# Schema embedding pipeline with mocked dependencies
# ---------------------------------------------------------------------------

class TestSchemaEmbeddingPipelineIntegration:
    async def test_process_table_with_embedding(self) -> None:
        mock_embedder = MagicMock()
        mock_embedder.embed = AsyncMock(return_value=[0.1, 0.2, 0.3])
        mock_embedder.embed_batch = AsyncMock(
            return_value=[
                EmbeddingResult(id="t1:table:orders", dense_vector=[0.1, 0.2, 0.3]),
                EmbeddingResult(id="t1:column:orders.id", dense_vector=[0.4, 0.5, 0.6]),
            ]
        )
        mock_repo = MagicMock()
        mock_repo.upsert_points = AsyncMock(return_value=2)
        mock_repo.ensure_collection = AsyncMock()
    
        pipeline = SchemaEmbeddingPipeline(
            embedding_service=mock_embedder,
            vector_repository=mock_repo,
        )
        table = ExtractedTable(
            name="orders",
            columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INTEGER", is_nullable=False, is_primary_key=True)],
        )
        count = await pipeline.process_table(table, tenant_id="t1")
        assert count >= 2
        assert mock_repo.upsert_points.await_count >= 1

    async def test_process_table_no_repository(self) -> None:
        mock_embedder = MagicMock()
        mock_embedder.embed = AsyncMock(return_value=[0.1, 0.2, 0.3])
        mock_embedder.embed_batch = AsyncMock(
            return_value=[
                EmbeddingResult(id="t1:table:orders", dense_vector=[0.1, 0.2, 0.3]),
            ]
        )

        pipeline = SchemaEmbeddingPipeline(embedding_service=mock_embedder)
        table = ExtractedTable(
            name="orders",
            columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INTEGER", is_nullable=False, is_primary_key=True)],
        )
        count = await pipeline.process_table(table, tenant_id="t1")
        assert count >= 1
