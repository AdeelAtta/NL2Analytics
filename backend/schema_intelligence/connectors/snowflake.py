from __future__ import annotations

import asyncio
from typing import Any

import snowflake.connector

from schema_intelligence.connectors.base import (
    BaseConnector,
    ConnectorConfig,
    ExtractedColumn,
    ExtractedSchemaInfo,
    ExtractedTable,
    ForeignKeyRef,
)


class SnowflakeConnector(BaseConnector):
    def __init__(self) -> None:
        self._conn: snowflake.connector.SnowflakeConnection | None = None
        self._config: ConnectorConfig | None = None

    async def connect(self, config: ConnectorConfig) -> None:
        self._config = config
        self._conn = await asyncio.to_thread(
            snowflake.connector.connect,
            user=config.username,
            password=config.password,
            account=config.host,
            database=config.database,
            schema="PUBLIC",
            warehouse=config.extra.get("warehouse"),
            role=config.extra.get("role"),
            login_timeout=config.timeout_seconds,
        )

    async def _execute(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> list[tuple[Any, ...]]:
        assert self._conn is not None

        def _run() -> list[tuple[Any, ...]]:
            cur = self._conn.cursor()
            try:
                if params:
                    cur.execute(query, params)
                else:
                    cur.execute(query)
                return list(cur.fetchall())
            finally:
                cur.close()

        return await asyncio.to_thread(_run)

    async def extract_schemas(self) -> list[ExtractedSchemaInfo]:
        rows = await self._execute(
            "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA "
            "WHERE SCHEMA_NAME NOT IN ('INFORMATION_SCHEMA') "
            "ORDER BY SCHEMA_NAME"
        )
        return [ExtractedSchemaInfo(name=row[0], tables=[]) for row in rows]

    async def extract_tables(self, schema_name: str) -> list[ExtractedTable]:
        rows = await self._execute(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE' "
            "ORDER BY TABLE_NAME",
            (schema_name,),
        )
        return [ExtractedTable(name=row[0], columns=[]) for row in rows]

    async def extract_columns(
        self,
        schema_name: str,
        table_name: str,
    ) -> list[ExtractedColumn]:
        pk_rows = await self._execute(
            "SELECT kcu.COLUMN_NAME "
            "FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc "
            "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu "
            "ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME "
            "AND tc.CONSTRAINT_SCHEMA = kcu.CONSTRAINT_SCHEMA "
            "AND tc.TABLE_NAME = kcu.TABLE_NAME "
            "WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY' "
            "AND tc.TABLE_SCHEMA = %s AND tc.TABLE_NAME = %s",
            (schema_name, table_name),
        )
        pk_columns = {row[0] for row in pk_rows}

        fk_rows = await self._execute(
            "SELECT "
            "kcu.COLUMN_NAME, "
            "kcu2.TABLE_NAME AS REF_TABLE, "
            "kcu2.COLUMN_NAME AS REF_COLUMN "
            "FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc "
            "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu "
            "ON rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME "
            "AND rc.CONSTRAINT_SCHEMA = kcu.CONSTRAINT_SCHEMA "
            "AND rc.CONSTRAINT_CATALOG = kcu.CONSTRAINT_CATALOG "
            "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu2 "
            "ON rc.UNIQUE_CONSTRAINT_NAME = kcu2.CONSTRAINT_NAME "
            "AND rc.UNIQUE_CONSTRAINT_SCHEMA = kcu2.CONSTRAINT_SCHEMA "
            "AND rc.UNIQUE_CONSTRAINT_CATALOG = kcu2.CONSTRAINT_CATALOG "
            "WHERE kcu.TABLE_SCHEMA = %s AND kcu.TABLE_NAME = %s",
            (schema_name, table_name),
        )
        fk_map: dict[str, ForeignKeyRef] = {}
        for row in fk_rows:
            fk_map[row[0]] = ForeignKeyRef(ref_table=row[1], ref_column=row[2])

        col_rows = await self._execute(
            "SELECT "
            "COLUMN_NAME, "
            "ORDINAL_POSITION, "
            "DATA_TYPE, "
            "IS_NULLABLE, "
            "COLUMN_DEFAULT, "
            "CHARACTER_MAXIMUM_LENGTH, "
            "NUMERIC_PRECISION, "
            "NUMERIC_SCALE, "
            "COMMENT "
            "FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
            "ORDER BY ORDINAL_POSITION",
            (schema_name, table_name),
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
        rows = await self._execute(
            "SELECT "
            "kcu.TABLE_CATALOG AS SCHEMA_NAME, "
            "kcu.TABLE_NAME, "
            "kcu.COLUMN_NAME, "
            "kcu2.TABLE_CATALOG AS REF_CATALOG, "
            "kcu2.TABLE_NAME AS REF_TABLE, "
            "kcu2.COLUMN_NAME AS REF_COLUMN, "
            "rc.CONSTRAINT_NAME "
            "FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc "
            "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu "
            "ON rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME "
            "AND rc.CONSTRAINT_SCHEMA = kcu.CONSTRAINT_SCHEMA "
            "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu2 "
            "ON rc.UNIQUE_CONSTRAINT_NAME = kcu2.CONSTRAINT_NAME "
            "AND rc.UNIQUE_CONSTRAINT_SCHEMA = kcu2.CONSTRAINT_SCHEMA "
            "WHERE kcu.TABLE_SCHEMA NOT IN ('INFORMATION_SCHEMA') "
            "ORDER BY kcu.TABLE_SCHEMA, kcu.TABLE_NAME, kcu.ORDINAL_POSITION"
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
        if self._conn is not None:
            await asyncio.to_thread(self._conn.close)
            self._conn = None
