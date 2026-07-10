from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from schema_intelligence.connectors.base import ConnectorConfig
from schema_intelligence.connectors.duckdb import DuckDBConnector


@pytest.fixture
def mock_conn() -> MagicMock:
    conn = MagicMock()
    conn.close = MagicMock()
    return conn


@pytest.fixture
def config() -> ConnectorConfig:
    return ConnectorConfig(
        host="localhost",
        port=0,
        database="testdb",
        username="user",
        password="pass",
    )


@pytest.fixture
async def connector(mock_conn: MagicMock, config: ConnectorConfig) -> DuckDBConnector:
    with patch(
        "schema_intelligence.connectors.duckdb.duckdb.connect",
        return_value=mock_conn,
    ):
        c = DuckDBConnector()
        await c.connect(config)
        yield c
        await c.close()


class TestDuckDBConnector:
    async def test_connect(self, config: ConnectorConfig) -> None:
        mock_duckdb_conn = MagicMock()
        mock_duckdb_conn.close = MagicMock()
        with patch(
            "schema_intelligence.connectors.duckdb.duckdb.connect",
            return_value=mock_duckdb_conn,
        ) as mock_connect:
            c = DuckDBConnector()
            await c.connect(config)
            mock_connect.assert_called_once_with("testdb")
            assert c._conn is mock_duckdb_conn
            await c.close()

    async def test_connect_in_memory(self) -> None:
        cfg = ConnectorConfig(
            host="localhost",
            port=0,
            database="",
            username="",
            password="",
        )
        mock_duckdb_conn = MagicMock()
        mock_duckdb_conn.close = MagicMock()
        with patch(
            "schema_intelligence.connectors.duckdb.duckdb.connect",
            return_value=mock_duckdb_conn,
        ) as mock_connect:
            c = DuckDBConnector()
            await c.connect(cfg)
            mock_connect.assert_called_once_with(":memory:")
            await c.close()

    async def test_extract_schemas(
        self, connector: DuckDBConnector
    ) -> None:
        with patch.object(
            connector,
            "_execute",
            AsyncMock(return_value=[("main",), ("analytics",)]),
        ):
            schemas = await connector.extract_schemas()
            assert len(schemas) == 2
            assert schemas[0].name == "main"
            assert schemas[1].name == "analytics"
            assert all(s.tables == [] for s in schemas)

    async def test_extract_schemas_excludes_system_schemas(
        self, connector: DuckDBConnector
    ) -> None:
        with patch.object(
            connector,
            "_execute",
            AsyncMock(return_value=[("main",)]),
        ) as mock_exec:
            schemas = await connector.extract_schemas()
            assert len(schemas) == 1
            assert schemas[0].name == "main"
            query = mock_exec.call_args[0][0]
            assert "pg_catalog" in query or "information_schema" in query

    async def test_extract_tables(
        self, connector: DuckDBConnector
    ) -> None:
        with patch.object(
            connector,
            "_execute",
            AsyncMock(return_value=[("users",), ("orders",)]),
        ):
            tables = await connector.extract_tables("main")
            assert len(tables) == 2
            assert tables[0].name == "users"
            assert tables[1].name == "orders"

    async def test_extract_tables_only_base_tables(
        self, connector: DuckDBConnector
    ) -> None:
        with patch.object(
            connector,
            "_execute",
            AsyncMock(return_value=[("users",)]),
        ):
            tables = await connector.extract_tables("main")
            assert len(tables) == 1
            assert tables[0].name == "users"

    async def test_extract_columns(
        self, connector: DuckDBConnector
    ) -> None:
        async def execute_side_effect(query: str, params: list | None = None) -> list:
            if "constraint_type = 'PRIMARY KEY'" in query:
                return [("id",)]
            if "constraint_type = 'FOREIGN KEY'" in query:
                return [("user_id", "users", "id")]
            return [
                ("id", 1, "INTEGER", "NO", None, None, None, None),
                ("user_id", 2, "BIGINT", "YES", None, None, 10, 0),
                ("email", 3, "VARCHAR", "NO", None, 255, None, None),
            ]

        with patch.object(connector, "_execute", AsyncMock(side_effect=execute_side_effect)):
            cols = await connector.extract_columns("main", "users")
            assert len(cols) == 3

            assert cols[0].name == "id"
            assert cols[0].is_primary_key is True
            assert cols[0].foreign_key is None

            assert cols[1].name == "user_id"
            assert cols[1].is_primary_key is False
            assert cols[1].foreign_key is not None
            assert cols[1].foreign_key.ref_table == "users"
            assert cols[1].foreign_key.ref_column == "id"
            assert cols[1].numeric_precision == 10
            assert cols[1].numeric_scale == 0

            assert cols[2].name == "email"
            assert cols[2].is_nullable is False
            assert cols[2].character_max_length == 255

    async def test_extract_columns_handles_nullable(
        self, connector: DuckDBConnector
    ) -> None:
        async def execute_side_effect(query: str, params: list | None = None) -> list:
            if "PRIMARY KEY" in query:
                return []
            if "FOREIGN KEY" in query:
                return []
            return [
                ("name", 1, "VARCHAR", "YES", None, None, None, None),
                ("age", 2, "INTEGER", "NO", None, None, None, None),
            ]

        with patch.object(connector, "_execute", AsyncMock(side_effect=execute_side_effect)):
            cols = await connector.extract_columns("main", "users")
            assert len(cols) == 2
            assert cols[0].is_nullable is True
            assert cols[1].is_nullable is False

    async def test_extract_columns_with_defaults(
        self, connector: DuckDBConnector
    ) -> None:
        async def execute_side_effect(query: str, params: list | None = None) -> list:
            if "PRIMARY KEY" in query:
                return [("id",)]
            if "FOREIGN KEY" in query:
                return []
            return [
                ("id", 1, "INTEGER", "NO", "nextval('seq')", None, None, None),
                ("created_at", 2, "TIMESTAMP", "YES", "now()", None, None, None),
            ]

        with patch.object(connector, "_execute", AsyncMock(side_effect=execute_side_effect)):
            cols = await connector.extract_columns("main", "users")
            assert cols[0].default_value == "nextval('seq')"
            assert cols[1].default_value == "now()"

    async def test_extract_empty_columns(
        self, connector: DuckDBConnector
    ) -> None:
        with patch.object(connector, "_execute", AsyncMock(return_value=[])):
            cols = await connector.extract_columns("main", "empty_table")
            assert cols == []

    async def test_extract_relationships(
        self, connector: DuckDBConnector
    ) -> None:
        with patch.object(
            connector,
            "_execute",
            AsyncMock(
                return_value=[
                    ("main", "orders", "user_id", "main", "users", "id", "orders_user_id_fkey"),
                ]
            ),
        ):
            rels = await connector.extract_relationships()
            assert len(rels) == 1
            assert rels[0]["table"] == "orders"
            assert rels[0]["ref_table"] == "users"
            assert rels[0]["constraint_name"] == "orders_user_id_fkey"
            assert rels[0]["schema"] == "main"
            assert rels[0]["ref_schema"] == "main"

    async def test_extract_relationships_empty(
        self, connector: DuckDBConnector
    ) -> None:
        with patch.object(connector, "_execute", AsyncMock(return_value=[])):
            rels = await connector.extract_relationships()
            assert rels == []

    async def test_close_closes_connection(self, config: ConnectorConfig) -> None:
        mock_conn = MagicMock()
        mock_conn.close = MagicMock()
        with patch(
            "schema_intelligence.connectors.duckdb.duckdb.connect",
            return_value=mock_conn,
        ):
            c = DuckDBConnector()
            await c.connect(config)
            assert c._conn is mock_conn
            await c.close()
            mock_conn.close.assert_called_once()
            assert c._conn is None

    async def test_double_close_is_safe(self, config: ConnectorConfig) -> None:
        mock_conn = MagicMock()
        mock_conn.close = MagicMock()
        with patch(
            "schema_intelligence.connectors.duckdb.duckdb.connect",
            return_value=mock_conn,
        ):
            c = DuckDBConnector()
            await c.connect(config)
            await c.close()
            await c.close()
            mock_conn.close.assert_called_once()

    async def test_register_in_registry(self) -> None:
        from schema_intelligence.connectors.base import ConnectorRegistry

        ConnectorRegistry.register("duckdb", DuckDBConnector)
        cls = ConnectorRegistry.get_connector("duckdb")
        assert cls is DuckDBConnector

    async def test_extract_schemas_single(
        self, connector: DuckDBConnector
    ) -> None:
        with patch.object(
            connector,
            "_execute",
            AsyncMock(return_value=[("main",)]),
        ):
            schemas = await connector.extract_schemas()
            assert len(schemas) == 1
            assert schemas[0].name == "main"
