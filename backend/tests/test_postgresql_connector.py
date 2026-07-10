from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from schema_intelligence.connectors.base import ConnectorConfig
from schema_intelligence.connectors.postgresql import PostgreSQLConnector


@pytest.fixture
def mock_conn() -> MagicMock:
    conn = MagicMock()
    conn.close = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    return conn


@pytest.fixture
def config() -> ConnectorConfig:
    return ConnectorConfig(
        host="localhost",
        port=5432,
        database="testdb",
        username="user",
        password="pass",
    )


@pytest.fixture
async def connector(mock_conn: MagicMock, config: ConnectorConfig) -> PostgreSQLConnector:
    with patch(
        "schema_intelligence.connectors.postgresql.asyncpg.connect",
        AsyncMock(return_value=mock_conn),
    ):
        c = PostgreSQLConnector()
        await c.connect(config)
        yield c
        await c.close()


class TestPostgreSQLConnector:
    async def test_connect(self, config: ConnectorConfig) -> None:
        mock_asyncpg_conn = MagicMock()
        mock_asyncpg_conn.close = AsyncMock()
        with patch(
            "schema_intelligence.connectors.postgresql.asyncpg.connect",
            AsyncMock(return_value=mock_asyncpg_conn),
        ) as mock_connect:
            c = PostgreSQLConnector()
            await c.connect(config)
            mock_connect.assert_awaited_once_with(
                host="localhost",
                port=5432,
                database="testdb",
                user="user",
                password="pass",
                ssl=True,
                timeout=30,
            )
            assert c._conn is mock_asyncpg_conn
            await c.close()

    async def test_extract_schemas(
        self, connector: PostgreSQLConnector, mock_conn: MagicMock
    ) -> None:
        mock_conn.fetch = AsyncMock(
            return_value=[
                {"schema_name": "public"},
                {"schema_name": "analytics"},
            ]
        )
        schemas = await connector.extract_schemas()
        assert len(schemas) == 2
        assert schemas[0].name == "public"
        assert schemas[1].name == "analytics"
        assert all(s.tables == [] for s in schemas)

    async def test_extract_schemas_excludes_system_schemas(
        self, connector: PostgreSQLConnector, mock_conn: MagicMock
    ) -> None:
        mock_conn.fetch = AsyncMock(
            return_value=[
                {"schema_name": "public"},
            ]
        )
        schemas = await connector.extract_schemas()
        assert len(schemas) == 1
        assert schemas[0].name == "public"
        call_args = mock_conn.fetch.await_args
        assert call_args is not None
        assert call_args.args[1] == "pg_catalog"
        assert call_args.args[2] == "information_schema"

    async def test_extract_tables(
        self, connector: PostgreSQLConnector, mock_conn: MagicMock
    ) -> None:
        mock_conn.fetch = AsyncMock(
            return_value=[
                {"table_name": "users", "comment": "User accounts", "row_count_estimate": 1000},
                {"table_name": "orders", "comment": None, "row_count_estimate": 500},
            ]
        )
        tables = await connector.extract_tables("public")
        assert len(tables) == 2
        assert tables[0].name == "users"
        assert tables[0].comment == "User accounts"
        assert tables[0].row_count_estimate == 1000
        assert tables[1].name == "orders"
        assert tables[1].row_count_estimate == 500

    async def test_extract_tables_only_base_tables(
        self, connector: PostgreSQLConnector, mock_conn: MagicMock
    ) -> None:
        mock_conn.fetch = AsyncMock(
            return_value=[
                {"table_name": "users", "comment": None, "row_count_estimate": None},
            ]
        )
        tables = await connector.extract_tables("public")
        assert len(tables) == 1
        assert tables[0].name == "users"

    async def test_extract_columns(
        self, connector: PostgreSQLConnector, mock_conn: MagicMock
    ) -> None:
        async def fetch_side_effect(query: str, *args: object) -> list[dict]:
            if "constraint_type = 'PRIMARY KEY'" in query:
                return [{"column_name": "id"}]
            if "constraint_type = 'FOREIGN KEY'" in query:
                return [{"column_name": "user_id", "ref_table": "users", "ref_column": "id"}]
            return [
                {
                    "column_name": "id",
                    "ordinal_position": 1,
                    "data_type": "integer",
                    "is_nullable": "NO",
                    "column_default": "nextval('users_id_seq'::regclass)",
                    "character_maximum_length": None,
                    "numeric_precision": None,
                    "numeric_scale": None,
                    "comment": "Primary key",
                },
                {
                    "column_name": "user_id",
                    "ordinal_position": 2,
                    "data_type": "bigint",
                    "is_nullable": "YES",
                    "column_default": None,
                    "character_maximum_length": None,
                    "numeric_precision": 10,
                    "numeric_scale": 0,
                    "comment": None,
                },
                {
                    "column_name": "email",
                    "ordinal_position": 3,
                    "data_type": "character varying",
                    "is_nullable": "NO",
                    "column_default": None,
                    "character_maximum_length": 255,
                    "numeric_precision": None,
                    "numeric_scale": None,
                    "comment": None,
                },
            ]

        mock_conn.fetch = AsyncMock(side_effect=fetch_side_effect)

        cols = await connector.extract_columns("public", "users")
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

    async def test_extract_relationships(
        self, connector: PostgreSQLConnector, mock_conn: MagicMock
    ) -> None:
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "table_schema": "public",
                    "table_name": "orders",
                    "column_name": "user_id",
                    "ref_schema": "public",
                    "ref_table": "users",
                    "ref_column": "id",
                    "constraint_name": "orders_user_id_fkey",
                },
            ]
        )
        rels = await connector.extract_relationships()
        assert len(rels) == 1
        assert rels[0]["table"] == "orders"
        assert rels[0]["ref_table"] == "users"
        assert rels[0]["constraint_name"] == "orders_user_id_fkey"

    async def test_close_closes_connection(self, config: ConnectorConfig) -> None:
        mock_conn = MagicMock()
        mock_conn.close = AsyncMock()
        with patch(
            "schema_intelligence.connectors.postgresql.asyncpg.connect",
            AsyncMock(return_value=mock_conn),
        ):
            c = PostgreSQLConnector()
            await c.connect(config)
            assert c._conn is mock_conn
            await c.close()
            mock_conn.close.assert_awaited_once()
            assert c._conn is None

    async def test_double_close_is_safe(self, config: ConnectorConfig) -> None:
        mock_conn = MagicMock()
        mock_conn.close = AsyncMock()
        with patch(
            "schema_intelligence.connectors.postgresql.asyncpg.connect",
            AsyncMock(return_value=mock_conn),
        ):
            c = PostgreSQLConnector()
            await c.connect(config)
            await c.close()
            await c.close()
            mock_conn.close.assert_awaited_once()

    async def test_extract_columns_empty_table(
        self, connector: PostgreSQLConnector, mock_conn: MagicMock
    ) -> None:
        mock_conn.fetch = AsyncMock(return_value=[])
        cols = await connector.extract_columns("public", "empty_table")
        assert cols == []

    async def test_register_in_registry(self) -> None:
        from schema_intelligence.connectors.base import ConnectorRegistry

        ConnectorRegistry.register("postgresql", PostgreSQLConnector)
        cls = ConnectorRegistry.get_connector("postgresql")
        assert cls is PostgreSQLConnector
