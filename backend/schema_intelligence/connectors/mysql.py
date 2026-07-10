from __future__ import annotations

from typing import Any

import aiomysql

from schema_intelligence.connectors.base import (
    BaseConnector,
    ConnectorConfig,
    ExtractedColumn,
    ExtractedSchemaInfo,
    ExtractedTable,
    ForeignKeyRef,
)


class MySQLConnector(BaseConnector):
    def __init__(self) -> None:
        self._conn: aiomysql.Connection | None = None
        self._config: ConnectorConfig | None = None

    async def connect(self, config: ConnectorConfig) -> None:
        self._config = config
        self._conn = await aiomysql.connect(
            host=config.host,
            port=config.port,
            db=config.database,
            user=config.username,
            password=config.password,
            ssl=config.ssl,
            connect_timeout=config.timeout_seconds,
        )

    async def _execute(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> list[tuple[Any, ...]]:
        assert self._conn is not None
        async with self._conn.cursor() as cursor:
            if params:
                await cursor.execute(query, params)
            else:
                await cursor.execute(query)
            return list(await cursor.fetchall())

    async def extract_schemas(self) -> list[ExtractedSchemaInfo]:
        rows = await self._execute(
            "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA "
            "WHERE SCHEMA_NAME NOT IN ('mysql', 'performance_schema', 'information_schema', 'sys') "
            "ORDER BY SCHEMA_NAME"
        )
        return [ExtractedSchemaInfo(name=row[0], tables=[]) for row in rows]

    async def extract_tables(self, schema_name: str) -> list[ExtractedTable]:
        rows = await self._execute(
            "SELECT TABLE_NAME FROM information_schema.TABLES "
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
            "FROM information_schema.TABLE_CONSTRAINTS tc "
            "JOIN information_schema.KEY_COLUMN_USAGE kcu "
            "ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME "
            "AND tc.TABLE_SCHEMA = kcu.TABLE_SCHEMA "
            "AND tc.TABLE_NAME = kcu.TABLE_NAME "
            "WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY' "
            "AND tc.TABLE_SCHEMA = %s AND tc.TABLE_NAME = %s",
            (schema_name, table_name),
        )
        pk_columns = {row[0] for row in pk_rows}

        fk_rows = await self._execute(
            "SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME "
            "FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE REFERENCED_TABLE_NAME IS NOT NULL "
            "AND TABLE_SCHEMA = %s AND TABLE_NAME = %s",
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
            "COLUMN_COMMENT "
            "FROM information_schema.COLUMNS "
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
            "TABLE_SCHEMA, "
            "TABLE_NAME, "
            "COLUMN_NAME, "
            "REFERENCED_TABLE_SCHEMA, "
            "REFERENCED_TABLE_NAME, "
            "REFERENCED_COLUMN_NAME, "
            "CONSTRAINT_NAME "
            "FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE REFERENCED_TABLE_NAME IS NOT NULL "
            "AND TABLE_SCHEMA NOT IN ('mysql', 'performance_schema', 'information_schema', 'sys') "
            "ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION"
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
            self._conn.close()
            self._conn = None
