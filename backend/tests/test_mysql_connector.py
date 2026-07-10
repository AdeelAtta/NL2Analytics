from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiomysql import Connection

from schema_intelligence.connectors.base import ConnectorConfig
from schema_intelligence.connectors.mysql import MySQLConnector


@pytest.fixture
def mock_conn() -> MagicMock:
    conn = MagicMock(spec=Connection)
    conn.close = MagicMock()
    return conn


@pytest.fixture
def config() -> ConnectorConfig:
    return ConnectorConfig(
        host="localhost",
        port=3306,
        database="testdb",
        username="user",
        password="pass",
    )


@pytest.fixture
async def connector(mock_conn: MagicMock, config: ConnectorConfig) -> MySQLConnector:
    with patch(
        "schema_intelligence.connectors.mysql.aiomysql.connect",
        AsyncMock(return_value=mock_conn),
    ):
        c = MySQLConnector()
        await c.connect(config)
        yield c
        await c.close()


class TestMySQLConnector:
    async def test_connect(self, config: ConnectorConfig) -> None:
        mock_aiomysql_conn = MagicMock(spec=Connection)
        mock_aiomysql_conn.close = MagicMock()
        with patch(
            "schema_intelligence.connectors.mysql.aiomysql.connect",
            AsyncMock(return_value=mock_aiomysql_conn),
        ) as mock_connect:
            c = MySQLConnector()
            await c.connect(config)
            mock_connect.assert_awaited_once_with(
                host="localhost",
                port=3306,
                db="testdb",
                user="user",
                password="pass",
                ssl=True,
                connect_timeout=30,
            )
            assert c._conn is mock_aiomysql_conn
            await c.close()

    async def test_extract_schemas(self, connector: MySQLConnector) -> None:
        with patch.object(
            connector,
            "_execute",
            AsyncMock(return_value=[("testdb",), ("analytics",)]),
        ):
            schemas = await connector.extract_schemas()
            assert len(schemas) == 2
            assert schemas[0].name == "testdb"
            assert schemas[1].name == "analytics"
            assert all(s.tables == [] for s in schemas)

    async def test_extract_schemas_excludes_system_schemas(
        self, connector: MySQLConnector
    ) -> None:
        with patch.object(
            connector,
            "_execute",
            AsyncMock(return_value=[("testdb",)]),
        ) as mock_exec:
            schemas = await connector.extract_schemas()
            assert len(schemas) == 1
            assert schemas[0].name == "testdb"
            query = mock_exec.call_args[0][0]
            assert "mysql" in query or "information_schema" in query

    async def test_extract_tables(self, connector: MySQLConnector) -> None:
        with patch.object(
            connector,
            "_execute",
            AsyncMock(return_value=[("users",), ("orders",)]),
        ):
            tables = await connector.extract_tables("testdb")
            assert len(tables) == 2
            assert tables[0].name == "users"
            assert tables[1].name == "orders"

    async def test_extract_tables_base_tables_only(self, connector: MySQLConnector) -> None:
        with patch.object(
            connector,
            "_execute",
            AsyncMock(return_value=[("users",)]),
        ):
            tables = await connector.extract_tables("testdb")
            assert len(tables) == 1
            assert tables[0].name == "users"

    async def test_extract_columns(self, connector: MySQLConnector) -> None:
        async def execute_side_effect(query: str, params: tuple | None = None) -> list:
            q_upper = query.upper()
            if "PRIMARY KEY" in q_upper:
                return [("id",)]
            if "REFERENCED_TABLE_NAME" in q_upper and params and len(params) == 2:
                return [("user_id", "users", "id")]
            return [
                ("id", 1, "int", "NO", None, None, None, None, "Primary key"),
                ("user_id", 2, "bigint", "YES", None, None, 10, 0, None),
                ("email", 3, "varchar", "NO", None, 255, None, None, None),
            ]

        with patch.object(connector, "_execute", AsyncMock(side_effect=execute_side_effect)):
            cols = await connector.extract_columns("testdb", "users")
            assert len(cols) == 3

            assert cols[0].name == "id"
            assert cols[0].is_primary_key is True
            assert cols[0].foreign_key is None
            assert cols[0].comment == "Primary key"

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

    async def test_extract_columns_handles_nullable(self, connector: MySQLConnector) -> None:
        async def execute_side_effect(query: str, params: tuple | None = None) -> list:
            if "PRIMARY KEY" in query.upper():
                return []
            if "REFERENCED_TABLE_NAME" in query.upper():
                return []
            return [
                ("name", 1, "varchar", "YES", None, 100, None, None, None),
                ("age", 2, "int", "NO", None, None, None, None, None),
            ]

        with patch.object(connector, "_execute", AsyncMock(side_effect=execute_side_effect)):
            cols = await connector.extract_columns("testdb", "users")
            assert len(cols) == 2
            assert cols[0].is_nullable is True
            assert cols[1].is_nullable is False

    async def test_extract_columns_with_defaults(self, connector: MySQLConnector) -> None:
        async def execute_side_effect(query: str, params: tuple | None = None) -> list:
            if "PRIMARY KEY" in query.upper():
                return []
            if "REFERENCED_TABLE_NAME" in query.upper():
                return []
            return [
                ("status", 1, "enum('a','b')", "NO", "'active'", None, None, None, None),
                ("ts", 2, "timestamp", "YES", "CURRENT_TIMESTAMP", None, None, None, None),
            ]

        with patch.object(connector, "_execute", AsyncMock(side_effect=execute_side_effect)):
            cols = await connector.extract_columns("testdb", "users")
            assert cols[0].default_value == "'active'"
            assert cols[1].default_value == "CURRENT_TIMESTAMP"

    async def test_extract_empty_columns(self, connector: MySQLConnector) -> None:
        with patch.object(connector, "_execute", AsyncMock(return_value=[])):
            cols = await connector.extract_columns("testdb", "empty_table")
            assert cols == []

    async def test_extract_relationships(self, connector: MySQLConnector) -> None:
        with patch.object(
            connector,
            "_execute",
            AsyncMock(
                return_value=[
                    ("testdb", "orders", "user_id", "testdb", "users", "id", "fk_orders_user"),
                ]
            ),
        ):
            rels = await connector.extract_relationships()
            assert len(rels) == 1
            assert rels[0]["table"] == "orders"
            assert rels[0]["ref_table"] == "users"
            assert rels[0]["constraint_name"] == "fk_orders_user"

    async def test_extract_relationships_empty(self, connector: MySQLConnector) -> None:
        with patch.object(connector, "_execute", AsyncMock(return_value=[])):
            rels = await connector.extract_relationships()
            assert rels == []

    async def test_close_closes_connection(self, config: ConnectorConfig) -> None:
        mock_conn = MagicMock(spec=Connection)
        mock_conn.close = MagicMock()
        with patch(
            "schema_intelligence.connectors.mysql.aiomysql.connect",
            AsyncMock(return_value=mock_conn),
        ):
            c = MySQLConnector()
            await c.connect(config)
            assert c._conn is mock_conn
            await c.close()
            mock_conn.close.assert_called_once()
            assert c._conn is None

    async def test_double_close_is_safe(self, config: ConnectorConfig) -> None:
        mock_conn = MagicMock(spec=Connection)
        mock_conn.close = MagicMock()
        with patch(
            "schema_intelligence.connectors.mysql.aiomysql.connect",
            AsyncMock(return_value=mock_conn),
        ):
            c = MySQLConnector()
            await c.connect(config)
            await c.close()
            await c.close()
            mock_conn.close.assert_called_once()

    async def test_register_in_registry(self) -> None:
        from schema_intelligence.connectors.base import ConnectorRegistry

        ConnectorRegistry.register("mysql", MySQLConnector)
        cls = ConnectorRegistry.get_connector("mysql")
        assert cls is MySQLConnector
