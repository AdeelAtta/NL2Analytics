from __future__ import annotations

from typing import Any

import pytest

from schema_intelligence.connectors.base import (
    BaseConnector,
    ConnectorConfig,
    ConnectorRegistry,
    ExtractedColumn,
    ExtractedSchema,
    ExtractedSchemaInfo,
    ExtractedTable,
    ForeignKeyRef,
)


class TestConnectorConfig:
    def test_minimal_config(self) -> None:
        cfg = ConnectorConfig(
            host="localhost", port=5432, database="test", username="u", password="p"
        )
        assert cfg.host == "localhost"
        assert cfg.port == 5432
        assert cfg.ssl is True
        assert cfg.timeout_seconds == 30
        assert cfg.schema_filter is None
        assert cfg.extra == {}

    def test_full_config(self) -> None:
        cfg = ConnectorConfig(
            host="db.example.com",
            port=3306,
            database="analytics",
            username="admin",
            password="secret",
            schema_filter=["public", "analytics"],
            ssl=False,
            timeout_seconds=60,
            extra={"charset": "utf8mb4"},
        )
        assert cfg.schema_filter == ["public", "analytics"]
        assert cfg.extra == {"charset": "utf8mb4"}


class TestForeignKeyRef:
    def test_valid_ref(self) -> None:
        ref = ForeignKeyRef(ref_table="orders", ref_column="user_id")
        assert ref.ref_table == "orders"
        assert ref.ref_column == "user_id"


class TestExtractedColumn:
    def test_minimal_column(self) -> None:
        col = ExtractedColumn(name="id", ordinal_position=1, data_type="integer", is_nullable=False)
        assert col.is_primary_key is False
        assert col.default_value is None
        assert col.foreign_key is None

    def test_full_column(self) -> None:
        fk = ForeignKeyRef(ref_table="users", ref_column="id")
        col = ExtractedColumn(
            name="user_id",
            ordinal_position=2,
            data_type="bigint",
            is_nullable=True,
            is_primary_key=False,
            default_value=None,
            foreign_key=fk,
            comment="FK to users",
            character_max_length=None,
            numeric_precision=10,
            numeric_scale=0,
        )
        assert col.foreign_key is not None
        assert col.foreign_key.ref_table == "users"
        assert col.comment == "FK to users"

    def test_primary_key_column(self) -> None:
        col = ExtractedColumn(
            name="id",
            ordinal_position=1,
            data_type="serial",
            is_nullable=False,
            is_primary_key=True,
        )
        assert col.is_primary_key is True


class TestExtractedTable:
    def test_table_with_columns(self) -> None:
        cols = [
            ExtractedColumn(name="id", ordinal_position=1, data_type="integer", is_nullable=False),
            ExtractedColumn(name="name", ordinal_position=2, data_type="varchar", is_nullable=True),
        ]
        table = ExtractedTable(
            name="users", columns=cols, ddl="CREATE TABLE users (...)", comment="User accounts"
        )
        assert len(table.columns) == 2
        assert table.ddl == "CREATE TABLE users (...)"
        assert table.comment == "User accounts"
        assert table.row_count_estimate is None


class TestExtractedSchemaInfo:
    def test_schema_with_tables(self) -> None:
        table = ExtractedTable(name="orders", columns=[])
        schema = ExtractedSchemaInfo(name="public", tables=[table])
        assert schema.name == "public"
        assert len(schema.tables) == 1


class TestExtractedSchema:
    def test_full_schema(self) -> None:
        schema_info = ExtractedSchemaInfo(name="public", tables=[])
        extracted = ExtractedSchema(
            database_name="testdb", db_type="postgresql", schemas=[schema_info]
        )
        assert extracted.database_name == "testdb"
        assert extracted.db_type == "postgresql"
        assert len(extracted.schemas) == 1


class TestBaseConnector:
    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError):
            BaseConnector()  # type: ignore[abstract]

    def test_concrete_subclass_must_implement_all_methods(self) -> None:
        with pytest.raises(TypeError):
            type("IncompleteConnector", (BaseConnector,), {})()

    def test_concrete_subclass_is_valid(self) -> None:
        class MockConnector(BaseConnector):
            async def connect(self, config: ConnectorConfig) -> None:
                pass

            async def extract_schemas(self) -> list[ExtractedSchemaInfo]:
                return []

            async def extract_tables(self, schema_name: str) -> list[ExtractedTable]:
                return []

            async def extract_columns(
                self, schema_name: str, table_name: str
            ) -> list[ExtractedColumn]:
                return []

            async def extract_relationships(self) -> list[dict[str, Any]]:
                return []

            async def close(self) -> None:
                pass

        connector = MockConnector()
        assert isinstance(connector, BaseConnector)

    async def test_async_context_manager(self) -> None:
        class MockConnector(BaseConnector):
            closed = False

            async def connect(self, config: ConnectorConfig) -> None:
                pass

            async def extract_schemas(self) -> list[ExtractedSchemaInfo]:
                return []

            async def extract_tables(self, schema_name: str) -> list[ExtractedTable]:
                return []

            async def extract_columns(
                self, schema_name: str, table_name: str
            ) -> list[ExtractedColumn]:
                return []

            async def extract_relationships(self) -> list[dict[str, Any]]:
                return []

            async def close(self) -> None:
                self.closed = True

        async with MockConnector() as conn:
            assert isinstance(conn, MockConnector)
        assert conn.closed


class TestConnectorRegistry:
    def setup_method(self) -> None:
        ConnectorRegistry._connectors.clear()

    def _make_mock_connector(self, name: str = "Mock") -> type[BaseConnector]:
        class _Mock(BaseConnector):
            async def connect(self, config: ConnectorConfig) -> None:
                pass

            async def extract_schemas(self) -> list[ExtractedSchemaInfo]:
                return []

            async def extract_tables(self, schema_name: str) -> list[ExtractedTable]:
                return []

            async def extract_columns(
                self, schema_name: str, table_name: str
            ) -> list[ExtractedColumn]:
                return []

            async def extract_relationships(self) -> list[dict[str, Any]]:
                return []

            async def close(self) -> None:
                pass

        _Mock.__name__ = name
        return _Mock

    def test_register_and_get(self) -> None:
        mock_cls = self._make_mock_connector("MockPGConnector")
        ConnectorRegistry.register("postgresql", mock_cls)
        cls = ConnectorRegistry.get_connector("postgresql")
        assert cls is mock_cls

    def test_get_unregistered_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            ConnectorRegistry.get_connector("nonexistent")

    def test_list_types(self) -> None:
        mock_cls = self._make_mock_connector("MockConnector")
        ConnectorRegistry.register("test_type", mock_cls)
        types = ConnectorRegistry.list_types()
        assert "test_type" in types
