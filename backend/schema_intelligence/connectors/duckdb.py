from __future__ import annotations

import asyncio
from typing import Any

import duckdb

from schema_intelligence.connectors.base import (
    BaseConnector,
    ConnectorConfig,
    ExtractedColumn,
    ExtractedSchemaInfo,
    ExtractedTable,
    ForeignKeyRef,
)


class DuckDBConnector(BaseConnector):
    def __init__(self) -> None:
        self._conn: duckdb.DuckDBPyConnection | None = None
        self._config: ConnectorConfig | None = None

    async def connect(self, config: ConnectorConfig) -> None:
        self._config = config
        db_path = config.database or ":memory:"
        self._conn = await asyncio.to_thread(duckdb.connect, db_path)

    async def _execute(self, query: str, params: list[Any] | None = None) -> list[tuple[Any, ...]]:
        assert self._conn is not None
        if params:
            result = await asyncio.to_thread(
                lambda q=query, p=params: self._conn.execute(q, p).fetchall()
            )
        else:
            result = await asyncio.to_thread(
                lambda q=query: self._conn.execute(q).fetchall()
            )
        return result

    async def extract_schemas(self) -> list[ExtractedSchemaInfo]:
        rows = await self._execute(
            """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema')
            ORDER BY schema_name
            """
        )
        return [ExtractedSchemaInfo(name=row[0], tables=[]) for row in rows]

    async def extract_tables(self, schema_name: str) -> list[ExtractedTable]:
        rows = await self._execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = ? AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """,
            [schema_name],
        )
        return [ExtractedTable(name=row[0], columns=[]) for row in rows]

    async def extract_columns(
        self,
        schema_name: str,
        table_name: str,
    ) -> list[ExtractedColumn]:
        pk_rows = await self._execute(
            """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
                AND tc.table_name = kcu.table_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
                AND tc.table_schema = ? AND tc.table_name = ?
            """,
            [schema_name, table_name],
        )
        pk_columns = {row[0] for row in pk_rows}

        fk_rows = await self._execute(
            """
            SELECT
                kcu.column_name,
                kcu2.table_name AS ref_table,
                kcu2.column_name AS ref_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
                AND tc.table_name = kcu.table_name
            JOIN information_schema.referential_constraints rc
                ON tc.constraint_name = rc.constraint_name
                AND tc.constraint_schema = rc.constraint_schema
                AND tc.constraint_catalog = rc.constraint_catalog
            JOIN information_schema.key_column_usage kcu2
                ON rc.unique_constraint_name = kcu2.constraint_name
                AND rc.unique_constraint_schema = kcu2.constraint_schema
                AND rc.unique_constraint_catalog = kcu2.constraint_catalog
                AND (kcu.position_in_unique_constraint IS NULL
                     OR kcu.position_in_unique_constraint = kcu2.ordinal_position)
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = ? AND tc.table_name = ?
            """,
            [schema_name, table_name],
        )
        fk_map: dict[str, ForeignKeyRef] = {}
        for row in fk_rows:
            fk_map[row[0]] = ForeignKeyRef(ref_table=row[1], ref_column=row[2])

        col_rows = await self._execute(
            """
            SELECT
                column_name,
                ordinal_position,
                data_type,
                is_nullable,
                column_default,
                character_maximum_length,
                numeric_precision,
                numeric_scale
            FROM information_schema.columns
            WHERE table_schema = ? AND table_name = ?
            ORDER BY ordinal_position
            """,
            [schema_name, table_name],
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
                comment=None,
                character_max_length=row[5],
                numeric_precision=row[6],
                numeric_scale=row[7],
            )
            for row in col_rows
        ]

    async def extract_relationships(self) -> list[dict[str, Any]]:
        rows = await self._execute(
            """
            SELECT
                tc.table_schema,
                tc.table_name,
                kcu.column_name,
                kcu2.table_schema AS ref_schema,
                kcu2.table_name AS ref_table,
                kcu2.column_name AS ref_column,
                tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
                AND tc.table_name = kcu.table_name
            JOIN information_schema.referential_constraints rc
                ON tc.constraint_name = rc.constraint_name
                AND tc.constraint_schema = rc.constraint_schema
                AND tc.constraint_catalog = rc.constraint_catalog
            JOIN information_schema.key_column_usage kcu2
                ON rc.unique_constraint_name = kcu2.constraint_name
                AND rc.unique_constraint_schema = kcu2.constraint_schema
                AND rc.unique_constraint_catalog = kcu2.constraint_catalog
                AND (kcu.position_in_unique_constraint IS NULL
                     OR kcu.position_in_unique_constraint = kcu2.ordinal_position)
            WHERE tc.constraint_type = 'FOREIGN KEY'
            ORDER BY tc.table_schema, tc.table_name, kcu.ordinal_position
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
        if self._conn is not None:
            await asyncio.to_thread(self._conn.close)
            self._conn = None
