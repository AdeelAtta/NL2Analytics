from __future__ import annotations

from typing import Any

import asyncpg

from schema_intelligence.connectors.base import (
    BaseConnector,
    ConnectorConfig,
    ExtractedColumn,
    ExtractedSchemaInfo,
    ExtractedTable,
    ForeignKeyRef,
)


class PostgreSQLConnector(BaseConnector):
    def __init__(self) -> None:
        self._conn: asyncpg.Connection | None = None
        self._config: ConnectorConfig | None = None

    async def connect(self, config: ConnectorConfig) -> None:
        self._config = config
        self._conn = await asyncpg.connect(
            host=config.host,
            port=config.port,
            database=config.database,
            user=config.username,
            password=config.password,
            ssl=config.ssl,
            timeout=config.timeout_seconds,
        )

    async def extract_schemas(self) -> list[ExtractedSchemaInfo]:
        assert self._conn is not None
        exclude = ("pg_catalog", "information_schema", "pg_toast")
        rows = await self._conn.fetch(
            """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ($1, $2, $3)
            ORDER BY schema_name
            """,
            *exclude,
        )
        return [ExtractedSchemaInfo(name=row["schema_name"], tables=[]) for row in rows]

    async def extract_tables(self, schema_name: str) -> list[ExtractedTable]:
        assert self._conn is not None
        rows = await self._conn.fetch(
            """
            SELECT
                t.table_name,
                pg_catalog.obj_description(
                    pg_catalog.pg_class.oid, 'pg_class'
                ) AS comment,
                pg_catalog.pg_class.reltuples::bigint AS row_count_estimate
            FROM information_schema.tables t
            LEFT JOIN pg_catalog.pg_class
                ON pg_catalog.pg_class.relname = t.table_name
                AND pg_catalog.pg_class.relnamespace = (
                    SELECT oid FROM pg_catalog.pg_namespace
                    WHERE nspname = t.table_schema
                )
            WHERE t.table_schema = $1
                AND t.table_type = 'BASE TABLE'
            ORDER BY t.table_name
            """,
            schema_name,
        )
        return [
            ExtractedTable(
                name=row["table_name"],
                columns=[],
                comment=row["comment"],
                row_count_estimate=row["row_count_estimate"],
            )
            for row in rows
        ]

    async def extract_columns(
        self,
        schema_name: str,
        table_name: str,
    ) -> list[ExtractedColumn]:
        assert self._conn is not None

        pk_rows = await self._conn.fetch(
            """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
                AND tc.table_name = kcu.table_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
                AND tc.table_schema = $1
                AND tc.table_name = $2
            """,
            schema_name,
            table_name,
        )
        pk_columns = {row["column_name"] for row in pk_rows}

        fk_rows = await self._conn.fetch(
            """
            SELECT
                kcu.column_name,
                ccu.table_name AS ref_table,
                ccu.column_name AS ref_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
                AND tc.table_name = kcu.table_name
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
                AND tc.table_schema = ccu.table_schema
                AND tc.table_name = ccu.table_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = $1
                AND tc.table_name = $2
            """,
            schema_name,
            table_name,
        )
        fk_map: dict[str, ForeignKeyRef] = {
            row["column_name"]: ForeignKeyRef(
                ref_table=row["ref_table"],
                ref_column=row["ref_column"],
            )
            for row in fk_rows
        }

        col_rows = await self._conn.fetch(
            """
            SELECT
                column_name,
                ordinal_position,
                data_type,
                is_nullable,
                column_default,
                character_maximum_length,
                numeric_precision,
                numeric_scale,
                pg_catalog.col_description(
                    (SELECT oid FROM pg_catalog.pg_class
                     WHERE relname = $2
                       AND relnamespace = (
                           SELECT oid FROM pg_catalog.pg_namespace
                           WHERE nspname = $1
                       )),
                    ordinal_position
                ) AS comment
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
            ORDER BY ordinal_position
            """,
            schema_name,
            table_name,
        )

        return [
            ExtractedColumn(
                name=row["column_name"],
                ordinal_position=row["ordinal_position"],
                data_type=row["data_type"],
                is_nullable=row["is_nullable"] == "YES",
                is_primary_key=row["column_name"] in pk_columns,
                default_value=row["column_default"],
                foreign_key=fk_map.get(row["column_name"]),
                comment=row["comment"],
                character_max_length=row["character_maximum_length"],
                numeric_precision=row["numeric_precision"],
                numeric_scale=row["numeric_scale"],
            )
            for row in col_rows
        ]

    async def extract_relationships(self) -> list[dict[str, Any]]:
        assert self._conn is not None
        rows = await self._conn.fetch(
            """
            SELECT
                tc.table_schema,
                tc.table_name,
                kcu.column_name,
                ccu.table_schema AS ref_schema,
                ccu.table_name AS ref_table,
                ccu.column_name AS ref_column,
                tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
                AND tc.table_name = kcu.table_name
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
                AND tc.table_schema = ccu.table_schema
                AND tc.table_name = ccu.table_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            ORDER BY tc.table_schema, tc.table_name, kcu.ordinal_position
            """,
        )
        return [
            {
                "schema": row["table_schema"],
                "table": row["table_name"],
                "column": row["column_name"],
                "ref_schema": row["ref_schema"],
                "ref_table": row["ref_table"],
                "ref_column": row["ref_column"],
                "constraint_name": row["constraint_name"],
            }
            for row in rows
        ]

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
