from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from schema_intelligence.connectors.base import ConnectorConfig
from schema_intelligence.connectors.bigquery import BigQueryConnector


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.close = MagicMock()
    client.query = MagicMock()

    def make_rows(data: list[tuple]) -> MagicMock:
        mock_rows = []
        for values in data:
            r = MagicMock()
            r.values.return_value = values
            mock_rows.append(r)
        iter_result = MagicMock()
        iter_result.__iter__.return_value = iter(mock_rows)
        return iter_result

    client._make_rows = make_rows
    return client


@pytest.fixture
def config() -> ConnectorConfig:
    return ConnectorConfig(
        host="my-gcp-project",
        port=0,
        database="my_dataset",
        username="",
        password="",
    )


@pytest.fixture
async def connector(mock_client: MagicMock, config: ConnectorConfig) -> BigQueryConnector:
    with (
        patch(
            "schema_intelligence.connectors.bigquery.bigquery.Client",
            return_value=mock_client,
        ),
        patch(
            "schema_intelligence.connectors.bigquery.service_account.Credentials.from_service_account_file",
            return_value="mock_creds",
        ),
    ):
        c = BigQueryConnector()
        await c.connect(config)
        yield c
        await c.close()


class TestBigQueryConnector:
    async def test_connect(self) -> None:
        mock_bq_client = MagicMock()
        mock_bq_client.close = MagicMock()
        with patch(
            "schema_intelligence.connectors.bigquery.bigquery.Client",
            return_value=mock_bq_client,
        ) as mock_connect:
            c = BigQueryConnector()
            cfg = ConnectorConfig(
                host="my-gcp-project", port=0, database="my_dataset",
                username="", password="",
            )
            await c.connect(cfg)
            mock_connect.assert_called_once_with(
                project="my-gcp-project", credentials=None
            )
            assert c._client is mock_bq_client
            await c.close()

    async def test_connect_with_credentials_path(self) -> None:
        mock_bq_client = MagicMock()
        mock_bq_client.close = MagicMock()
        cfg = ConnectorConfig(
            host="my-gcp-project", port=0, database="my_dataset",
            username="", password="",
            extra={"credentials_path": "/path/to/sa.json"},
        )
        with patch(
            "schema_intelligence.connectors.bigquery.bigquery.Client",
            return_value=mock_bq_client,
        ) as mock_connect:
            with patch(
                "schema_intelligence.connectors.bigquery.service_account.Credentials.from_service_account_file",
                return_value="mock_creds",
            ) as mock_creds:
                c = BigQueryConnector()
                await c.connect(cfg)
                mock_creds.assert_called_once_with("/path/to/sa.json")
                mock_connect.assert_called_once_with(
                    project="my-gcp-project", credentials="mock_creds"
                )
                await c.close()

    async def test_connect_with_credentials_json(self) -> None:
        mock_bq_client = MagicMock()
        mock_bq_client.close = MagicMock()
        cfg = ConnectorConfig(
            host="my-gcp-project",
            port=0,
            database="my_dataset",
            username="",
            password="",
            extra={"credentials_json": '{"type": "service_account"}'},
        )
        with patch(
            "schema_intelligence.connectors.bigquery.bigquery.Client",
            return_value=mock_bq_client,
        ):
            with patch(
                "schema_intelligence.connectors.bigquery.service_account.Credentials.from_service_account_info",
                return_value="mock_creds_json",
            ) as mock_creds:
                c = BigQueryConnector()
                await c.connect(cfg)
                mock_creds.assert_called_once_with({"type": "service_account"})
                await c.close()

    async def test_extract_schemas(
        self, connector: BigQueryConnector, mock_client: MagicMock
    ) -> None:
        ds1 = MagicMock()
        ds1.dataset_id = "my_dataset"
        ds2 = MagicMock()
        ds2.dataset_id = "analytics"
        mock_client.list_datasets.return_value = [ds1, ds2]

        schemas = await connector.extract_schemas()
        assert len(schemas) == 2
        assert schemas[0].name == "my_dataset"
        assert schemas[1].name == "analytics"
        assert all(s.tables == [] for s in schemas)

    async def test_extract_schemas_empty(
        self, connector: BigQueryConnector, mock_client: MagicMock
    ) -> None:
        mock_client.list_datasets.return_value = []
        schemas = await connector.extract_schemas()
        assert schemas == []

    async def test_extract_tables(
        self, connector: BigQueryConnector, mock_client: MagicMock
    ) -> None:
        def query_side_effect(sql: str, **kwargs: object) -> MagicMock:
            result = MagicMock()
            if "INFORMATION_SCHEMA.TABLES" in sql:
                r1 = MagicMock()
                r1.values.return_value = ("users",)
                r2 = MagicMock()
                r2.values.return_value = ("orders",)
                result.result.return_value = [r1, r2]
            else:
                result.result.return_value = []
            return result

        mock_client.query.side_effect = query_side_effect
        tables = await connector.extract_tables("my_dataset")
        assert len(tables) == 2
        assert tables[0].name == "users"
        assert tables[1].name == "orders"

    async def test_extract_tables_base_tables_only(
        self, connector: BigQueryConnector, mock_client: MagicMock
    ) -> None:
        def query_side_effect(sql: str, **kwargs: object) -> MagicMock:
            result = MagicMock()
            if "INFORMATION_SCHEMA.TABLES" in sql and "table_type = 'BASE TABLE'" in sql:
                r1 = MagicMock()
                r1.values.return_value = ("users",)
                result.result.return_value = [r1]
            else:
                result.result.return_value = []
            return result

        mock_client.query.side_effect = query_side_effect
        tables = await connector.extract_tables("my_dataset")
        assert len(tables) == 1
        assert tables[0].name == "users"

    async def test_extract_columns(self, connector: BigQueryConnector) -> None:
        call_count = 0

        async def execute_side_effect(
            sql: str, params: dict[str, str] | None = None
        ) -> list[tuple]:
            nonlocal call_count
            call_count += 1
            if "TABLE_CONSTRAINTS" in sql and "PRIMARY KEY" in sql:
                return [("id",)]
            if "REFERENTIAL_CONSTRAINTS" in sql:
                return [("user_id", "users", "id")]
            if "INFORMATION_SCHEMA.COLUMNS" in sql:
                return [
                    ("id", 1, "INT64", "NO", None, None, None, None, "Primary key"),
                    ("user_id", 2, "INT64", "YES", None, None, None, None, None),
                    ("email", 3, "STRING", "NO", None, 255, None, None, None),
                ]
            return []

        with patch.object(connector, "_execute_query", side_effect=execute_side_effect):
            cols = await connector.extract_columns("my_dataset", "users")
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

            assert cols[2].name == "email"
            assert cols[2].is_nullable is False
            assert cols[2].character_max_length == 255

    async def test_extract_columns_handles_nullable(self, connector: BigQueryConnector) -> None:
        async def execute_side_effect(
            sql: str, params: dict[str, str] | None = None
        ) -> list[tuple]:
            if "PRIMARY KEY" in sql:
                return []
            if "REFERENTIAL_CONSTRAINTS" in sql:
                return []
            return [
                ("name", 1, "STRING", "YES", None, 100, None, None, None),
                ("age", 2, "INT64", "NO", None, None, 10, 0, None),
            ]

        with patch.object(connector, "_execute_query", side_effect=execute_side_effect):
            cols = await connector.extract_columns("my_dataset", "users")
            assert len(cols) == 2
            assert cols[0].is_nullable is True
            assert cols[1].is_nullable is False

    async def test_extract_columns_with_defaults(self, connector: BigQueryConnector) -> None:
        async def execute_side_effect(
            sql: str, params: dict[str, str] | None = None
        ) -> list[tuple]:
            if "PRIMARY KEY" in sql:
                return [("id",)]
            if "REFERENTIAL_CONSTRAINTS" in sql:
                return []
            return [
                ("id", 1, "INT64", "NO", "GENERATED_BY_DEFAULT", None, None, None, None),
                ("ts", 2, "TIMESTAMP", "YES", "CURRENT_TIMESTAMP()", None, None, None, None),
            ]

        with patch.object(connector, "_execute_query", side_effect=execute_side_effect):
            cols = await connector.extract_columns("my_dataset", "users")
            assert "GENERATED_BY_DEFAULT" in cols[0].default_value
            assert "CURRENT_TIMESTAMP" in cols[1].default_value

    async def test_extract_empty_columns(self, connector: BigQueryConnector) -> None:
        with patch.object(connector, "_execute_query", return_value=[]):
            cols = await connector.extract_columns("my_dataset", "empty_table")
            assert cols == []

    async def test_extract_relationships(self, connector: BigQueryConnector) -> None:
        with patch.object(
            connector,
            "_execute_query",
            return_value=[
                ("my_dataset", "orders", "user_id", "my_dataset", "users", "id", "fk_orders_user"),
            ],
        ):
            rels = await connector.extract_relationships()
            assert len(rels) == 1
            assert rels[0]["table"] == "orders"
            assert rels[0]["ref_table"] == "users"
            assert rels[0]["constraint_name"] == "fk_orders_user"

    async def test_extract_relationships_empty(self, connector: BigQueryConnector) -> None:
        with patch.object(connector, "_execute_query", return_value=[]):
            rels = await connector.extract_relationships()
            assert rels == []

    async def test_close_closes_client(self, config: ConnectorConfig) -> None:
        mock_bq = MagicMock()
        mock_bq.close = MagicMock()
        with patch(
            "schema_intelligence.connectors.bigquery.bigquery.Client",
            return_value=mock_bq,
        ):
            c = BigQueryConnector()
            await c.connect(config)
            assert c._client is mock_bq
            await c.close()
            mock_bq.close.assert_called_once()
            assert c._client is None

    async def test_double_close_is_safe(self, config: ConnectorConfig) -> None:
        mock_bq = MagicMock()
        mock_bq.close = MagicMock()
        with patch(
            "schema_intelligence.connectors.bigquery.bigquery.Client",
            return_value=mock_bq,
        ):
            c = BigQueryConnector()
            await c.connect(config)
            await c.close()
            await c.close()
            mock_bq.close.assert_called_once()

    async def test_register_in_registry(self) -> None:
        from schema_intelligence.connectors.base import ConnectorRegistry

        ConnectorRegistry.register("bigquery", BigQueryConnector)
        cls = ConnectorRegistry.get_connector("bigquery")
        assert cls is BigQueryConnector
