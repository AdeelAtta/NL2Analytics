from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from schema_intelligence.connectors.base import ConnectorConfig
from schema_intelligence.connectors.snowflake import SnowflakeConnector


@pytest.fixture
def mock_conn() -> MagicMock:
    conn = MagicMock()
    conn.close = MagicMock()
    return conn


@pytest.fixture
def config() -> ConnectorConfig:
    return ConnectorConfig(
        host="myaccount.snowflakecomputing.com",
        port=443,
        database="MYDB",
        username="user",
        password="pass",
        extra={"warehouse": "COMPUTE_WH", "role": "SYSADMIN"},
    )


@pytest.fixture
async def connector(mock_conn: MagicMock, config: ConnectorConfig) -> SnowflakeConnector:
    with patch(
        "schema_intelligence.connectors.snowflake.snowflake.connector.connect",
        return_value=mock_conn,
    ):
        c = SnowflakeConnector()
        await c.connect(config)
        yield c
        await c.close()


class TestSnowflakeConnector:
    async def test_connect(self, config: ConnectorConfig) -> None:
        mock_snowflake_conn = MagicMock()
        mock_snowflake_conn.close = MagicMock()
        with patch(
            "schema_intelligence.connectors.snowflake.snowflake.connector.connect",
            return_value=mock_snowflake_conn,
        ) as mock_connect:
            c = SnowflakeConnector()
            await c.connect(config)
            mock_connect.assert_called_once_with(
                user="user",
                password="pass",
                account="myaccount.snowflakecomputing.com",
                database="MYDB",
                schema="PUBLIC",
                warehouse="COMPUTE_WH",
                role="SYSADMIN",
                login_timeout=30,
            )
            assert c._conn is mock_snowflake_conn
            await c.close()

    async def test_extract_schemas(self, connector: SnowflakeConnector) -> None:
        with patch.object(
            connector,
            "_execute",
            return_value=[("PUBLIC",), ("ANALYTICS",)],
        ):
            schemas = await connector.extract_schemas()
            assert len(schemas) == 2
            assert schemas[0].name == "PUBLIC"
            assert schemas[1].name == "ANALYTICS"
            assert all(s.tables == [] for s in schemas)

    async def test_extract_schemas_excludes_system(
        self, connector: SnowflakeConnector
    ) -> None:
        with patch.object(
            connector,
            "_execute",
            return_value=[("PUBLIC",)],
        ) as mock_exec:
            schemas = await connector.extract_schemas()
            assert len(schemas) == 1
            assert schemas[0].name == "PUBLIC"
            query = mock_exec.call_args[0][0]
            assert "INFORMATION_SCHEMA" in query

    async def test_extract_tables(self, connector: SnowflakeConnector) -> None:
        with patch.object(
            connector,
            "_execute",
            return_value=[("USERS",), ("ORDERS",)],
        ):
            tables = await connector.extract_tables("PUBLIC")
            assert len(tables) == 2
            assert tables[0].name == "USERS"
            assert tables[1].name == "ORDERS"

    async def test_extract_tables_base_tables_only(self, connector: SnowflakeConnector) -> None:
        with patch.object(
            connector,
            "_execute",
            return_value=[("USERS",)],
        ):
            tables = await connector.extract_tables("PUBLIC")
            assert len(tables) == 1
            assert tables[0].name == "USERS"

    async def test_extract_columns(self, connector: SnowflakeConnector) -> None:
        async def execute_side_effect(query: str, params: tuple | None = None) -> list:
            q_upper = query.upper()
            if "PRIMARY KEY" in q_upper:
                return [("ID",)]
            if "REFERENTIAL_CONSTRAINTS" in q_upper:
                return [("USER_ID", "USERS", "ID")]
            return [
                ("ID", 1, "NUMBER", "NO", None, None, 38, 0, "Primary key"),
                ("USER_ID", 2, "NUMBER", "YES", None, None, 38, 0, None),
                ("EMAIL", 3, "VARCHAR", "NO", None, 255, None, None, None),
            ]

        with patch.object(connector, "_execute", side_effect=execute_side_effect):
            cols = await connector.extract_columns("PUBLIC", "USERS")
            assert len(cols) == 3

            assert cols[0].name == "ID"
            assert cols[0].is_primary_key is True
            assert cols[0].foreign_key is None
            assert cols[0].comment == "Primary key"

            assert cols[1].name == "USER_ID"
            assert cols[1].is_primary_key is False
            assert cols[1].foreign_key is not None
            assert cols[1].foreign_key.ref_table == "USERS"
            assert cols[1].foreign_key.ref_column == "ID"
            assert cols[1].numeric_precision == 38
            assert cols[1].numeric_scale == 0

            assert cols[2].name == "EMAIL"
            assert cols[2].is_nullable is False
            assert cols[2].character_max_length == 255

    async def test_extract_columns_handles_nullable(self, connector: SnowflakeConnector) -> None:
        async def execute_side_effect(query: str, params: tuple | None = None) -> list:
            if "PRIMARY KEY" in query.upper():
                return []
            if "REFERENTIAL_CONSTRAINTS" in query.upper():
                return []
            return [
                ("NAME", 1, "VARCHAR", "YES", None, 100, None, None, None),
                ("AGE", 2, "NUMBER", "NO", None, None, 10, 0, None),
            ]

        with patch.object(connector, "_execute", side_effect=execute_side_effect):
            cols = await connector.extract_columns("PUBLIC", "USERS")
            assert len(cols) == 2
            assert cols[0].is_nullable is True
            assert cols[1].is_nullable is False

    async def test_extract_columns_with_defaults(self, connector: SnowflakeConnector) -> None:
        async def execute_side_effect(query: str, params: tuple | None = None) -> list:
            if "PRIMARY KEY" in query.upper():
                return [("ID",)]
            if "REFERENTIAL_CONSTRAINTS" in query.upper():
                return []
            return [
                ("ID", 1, "NUMBER", "NO", "MYDB.PUBLIC.SEQ.NEXTVAL", None, 38, 0, None),
                ("TS", 2, "TIMESTAMP_LTZ", "YES", "CURRENT_TIMESTAMP()", None, None, None, None),
            ]

        with patch.object(connector, "_execute", side_effect=execute_side_effect):
            cols = await connector.extract_columns("PUBLIC", "USERS")
            assert "NEXTVAL" in cols[0].default_value
            assert "CURRENT_TIMESTAMP" in cols[1].default_value

    async def test_extract_empty_columns(self, connector: SnowflakeConnector) -> None:
        with patch.object(connector, "_execute", return_value=[]):
            cols = await connector.extract_columns("PUBLIC", "EMPTY_TABLE")
            assert cols == []

    async def test_extract_relationships(self, connector: SnowflakeConnector) -> None:
        with patch.object(
            connector,
            "_execute",
            return_value=[
                ("MYDB", "ORDERS", "USER_ID", "MYDB", "USERS", "ID", "FK_ORDERS_USER"),
            ],
        ):
            rels = await connector.extract_relationships()
            assert len(rels) == 1
            assert rels[0]["table"] == "ORDERS"
            assert rels[0]["ref_table"] == "USERS"
            assert rels[0]["constraint_name"] == "FK_ORDERS_USER"

    async def test_extract_relationships_empty(self, connector: SnowflakeConnector) -> None:
        with patch.object(connector, "_execute", return_value=[]):
            rels = await connector.extract_relationships()
            assert rels == []

    async def test_close_closes_connection(self, config: ConnectorConfig) -> None:
        mock_conn = MagicMock()
        mock_conn.close = MagicMock()
        with patch(
            "schema_intelligence.connectors.snowflake.snowflake.connector.connect",
            return_value=mock_conn,
        ):
            c = SnowflakeConnector()
            await c.connect(config)
            assert c._conn is mock_conn
            await c.close()
            mock_conn.close.assert_called_once()
            assert c._conn is None

    async def test_double_close_is_safe(self, config: ConnectorConfig) -> None:
        mock_conn = MagicMock()
        mock_conn.close = MagicMock()
        with patch(
            "schema_intelligence.connectors.snowflake.snowflake.connector.connect",
            return_value=mock_conn,
        ):
            c = SnowflakeConnector()
            await c.connect(config)
            await c.close()
            await c.close()
            mock_conn.close.assert_called_once()

    async def test_register_in_registry(self) -> None:
        from schema_intelligence.connectors.base import ConnectorRegistry

        ConnectorRegistry.register("snowflake", SnowflakeConnector)
        cls = ConnectorRegistry.get_connector("snowflake")
        assert cls is SnowflakeConnector
