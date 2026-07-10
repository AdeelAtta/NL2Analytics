from __future__ import annotations

import asyncio
import json
from typing import Any

from google.cloud import bigquery
from google.oauth2 import service_account

from schema_intelligence.connectors.base import (
    BaseConnector,
    ConnectorConfig,
    ExtractedColumn,
    ExtractedSchemaInfo,
    ExtractedTable,
    ForeignKeyRef,
)


class BigQueryConnector(BaseConnector):
    def __init__(self) -> None:
        self._client: bigquery.Client | None = None
        self._config: ConnectorConfig | None = None

    async def connect(self, config: ConnectorConfig) -> None:
        self._config = config
        creds = None
        credentials_path = config.extra.get("credentials_path")
        credentials_json = config.extra.get("credentials_json")
        if credentials_path:
            creds = service_account.Credentials.from_service_account_file(
                credentials_path
            )
        elif credentials_json:
            creds = service_account.Credentials.from_service_account_info(
                json.loads(credentials_json)
            )

        def _create_client() -> bigquery.Client:
            return bigquery.Client(project=config.host, credentials=creds)

        self._client = await asyncio.to_thread(_create_client)

    async def _execute_query(
        self, sql: str, params: dict[str, Any] | None = None
    ) -> list[tuple[Any, ...]]:
        assert self._client is not None

        def _run() -> list[tuple[Any, ...]]:
            job_config = None
            if params:
                job_config = bigquery.QueryJobConfig(
                    query_parameters=[
                        bigquery.ScalarQueryParameter(k, "STRING", v)
                        for k, v in params.items()
                    ]
                )
            rows = self._client.query(sql, job_config=job_config).result()
            return [tuple(r.values()) for r in rows]

        return await asyncio.to_thread(_run)

    async def extract_schemas(self) -> list[ExtractedSchemaInfo]:
        assert self._client is not None
        assert self._config is not None

        datasets = await asyncio.to_thread(
            lambda: list(self._client.list_datasets(project=self._config.host))
        )
        return [ExtractedSchemaInfo(name=d.dataset_id, tables=[]) for d in datasets]

    async def extract_tables(self, schema_name: str) -> list[ExtractedTable]:
        assert self._config is not None
        project = self._config.host
        rows = await self._execute_query(
            f"""
            SELECT table_name
            FROM `{project}.{schema_name}.INFORMATION_SCHEMA.TABLES`
            WHERE table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        )
        return [ExtractedTable(name=row[0], columns=[]) for row in rows]

    async def extract_columns(
        self,
        schema_name: str,
        table_name: str,
    ) -> list[ExtractedColumn]:
        assert self._config is not None
        project = self._config.host

        pk_rows = await self._execute_query(
            f"""
            SELECT kcu.column_name
            FROM `{project}.{schema_name}.INFORMATION_SCHEMA.TABLE_CONSTRAINTS` tc
            JOIN `{project}.{schema_name}.INFORMATION_SCHEMA.KEY_COLUMN_USAGE` kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_catalog = kcu.table_catalog
                AND tc.table_schema = kcu.table_schema
                AND tc.table_name = kcu.table_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
                AND tc.table_name = @table_name
            """,
            {"table_name": table_name},
        )
        pk_columns = {row[0] for row in pk_rows}

        fk_rows = await self._execute_query(
            f"""
            SELECT
                kcu.column_name,
                kcu2.table_name AS ref_table,
                kcu2.column_name AS ref_column
            FROM `{project}.{schema_name}.INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS` rc
            JOIN `{project}.{schema_name}.INFORMATION_SCHEMA.KEY_COLUMN_USAGE` kcu
                ON rc.constraint_name = kcu.constraint_name
                AND rc.constraint_catalog = kcu.constraint_catalog
                AND rc.constraint_schema = kcu.constraint_schema
            JOIN `{project}.{schema_name}.INFORMATION_SCHEMA.KEY_COLUMN_USAGE` kcu2
                ON rc.unique_constraint_name = kcu2.constraint_name
                AND rc.unique_constraint_catalog = kcu2.constraint_catalog
                AND rc.unique_constraint_schema = kcu2.constraint_schema
            WHERE kcu.table_name = @table_name
            """,
            {"table_name": table_name},
        )
        fk_map: dict[str, ForeignKeyRef] = {}
        for row in fk_rows:
            fk_map[row[0]] = ForeignKeyRef(ref_table=row[1], ref_column=row[2])

        col_rows = await self._execute_query(
            f"""
            SELECT
                column_name,
                ordinal_position,
                data_type,
                is_nullable,
                column_default,
                character_maximum_length,
                numeric_precision,
                numeric_scale,
                description
            FROM `{project}.{schema_name}.INFORMATION_SCHEMA.COLUMNS`
            WHERE table_name = @table_name
            ORDER BY ordinal_position
            """,
            {"table_name": table_name},
        )

        return [
            ExtractedColumn(
                name=row[0],
                ordinal_position=row[1],
                data_type=row[2],
                is_nullable=row[3] == "YES",
                is_primary_key=row[0] in pk_columns,
                default_value=row[4],
                foreign_key=fk_map.get(row[0]),
                comment=row[8],
                character_max_length=row[5],
                numeric_precision=row[6],
                numeric_scale=row[7],
            )
            for row in col_rows
        ]

    async def extract_relationships(self) -> list[dict[str, Any]]:
        assert self._config is not None
        project = self._config.host

        rows = await self._execute_query(
            f"""
            SELECT
                kcu.table_catalog AS schema_name,
                kcu.table_name,
                kcu.column_name,
                kcu2.table_catalog AS ref_catalog,
                kcu2.table_name AS ref_table,
                kcu2.column_name AS ref_column,
                rc.constraint_name
            FROM `{project}.{self._config.database}.INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS` rc
            JOIN `{project}.{self._config.database}.INFORMATION_SCHEMA.KEY_COLUMN_USAGE` kcu
                ON rc.constraint_name = kcu.constraint_name
                AND rc.constraint_catalog = kcu.constraint_catalog
                AND rc.constraint_schema = kcu.constraint_schema
            JOIN `{project}.{self._config.database}.INFORMATION_SCHEMA.KEY_COLUMN_USAGE` kcu2
                ON rc.unique_constraint_name = kcu2.constraint_name
                AND rc.unique_constraint_catalog = kcu2.constraint_catalog
                AND rc.unique_constraint_schema = kcu2.constraint_schema
            ORDER BY kcu.table_catalog, kcu.table_name, kcu.ordinal_position
            """
        )
        return [
            {
                "schema": row[0],
                "table": row[1],
                "column": row[2],
                "ref_schema": row[3],
                "ref_table": row[4],
                "ref_column": row[5],
                "constraint_name": row[6],
            }
            for row in rows
        ]

    async def close(self) -> None:
        if self._client is not None:
            await asyncio.to_thread(self._client.close)
            self._client = None
