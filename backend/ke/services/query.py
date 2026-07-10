from __future__ import annotations

import logging
import re
from typing import Any

from ke.models.schema import Column as ColumnModel
from ke.models.schema import Table as TableModel
from ke.models.vector import HybridSearchParams, SearchResult
from ke.stores.schema.repository import ColumnRepository, TableRepository
from ke.stores.vector.embedding import EmbeddingService
from ke.stores.vector.repository import VectorRepository

logger = logging.getLogger(__name__)

_TYPE_MAP: dict[str, str] = {
    "integer": "INTEGER",
    "bigint": "BIGINT",
    "smallint": "SMALLINT",
    "tinyint": "TINYINT",
    "serial": "SERIAL",
    "bigserial": "BIGSERIAL",
    "text": "TEXT",
    "boolean": "BOOLEAN",
    "bool": "BOOLEAN",
    "real": "REAL",
    "float": "FLOAT",
    "double": "DOUBLE PRECISION",
    "numeric": "NUMERIC",
    "decimal": "DECIMAL",
    "money": "MONEY",
    "char": "CHAR",
    "varchar": "VARCHAR",
    "timestamp": "TIMESTAMP",
    "timestamptz": "TIMESTAMPTZ",
    "timestampt": "TIMESTAMP WITH TIME ZONE",
    "date": "DATE",
    "time": "TIME",
    "interval": "INTERVAL",
    "uuid": "UUID",
    "json": "JSON",
    "jsonb": "JSONB",
    "bytea": "BYTEA",
    "blob": "BLOB",
    "inet": "INET",
    "macaddr": "MACADDR",
    "point": "POINT",
}


def _to_ddl_type(data_type: str) -> str:
    lower = data_type.lower().strip()
    if lower in _TYPE_MAP:
        return _TYPE_MAP[lower]
    if re.match(r"^varchar\s*\(\d+\)$", lower):
        return data_type.upper()
    if re.match(r"^char\s*\(\d+\)$", lower):
        return data_type.upper()
    if re.match(r"^numeric\s*\(\d+,\s*\d+\)$", lower):
        return data_type.upper()
    if re.match(r"^decimal\s*\(\d+,\s*\d+\)$", lower):
        return data_type.upper()
    return data_type.upper()


class DDLRenderer:
    @staticmethod
    def render_table(table: TableModel, columns: list[ColumnModel]) -> str:
        parts: list[str] = [f"CREATE TABLE {table.name} ("]
        col_lines: list[str] = []
        pk_columns: list[str] = []

        for col in sorted(columns, key=lambda c: c.ordinal_position):
            ddl_type = _to_ddl_type(col.data_type)
            line = f"    {col.name} {ddl_type}"
            if col.is_nullable is False:
                line += " NOT NULL"
            if col.is_unique:
                line += " UNIQUE"
            if col.default_value is not None:
                line += f" DEFAULT {col.default_value}"
            if col.description:
                line += f" /* {col.description} */"
            col_lines.append(line)
            if col.is_primary_key:
                pk_columns.append(col.name)

        if pk_columns:
            col_lines.append(f"    PRIMARY KEY ({', '.join(pk_columns)})")

        fk_lines: list[str] = []
        for col in columns:
            if col.foreign_key_table and col.foreign_key_column:
                fk_lines.append(
                    f"    FOREIGN KEY ({col.name}) REFERENCES {col.foreign_key_table}({col.foreign_key_column})"
                )

        parts.append(",\n".join(col_lines))
        if fk_lines:
            parts[-1] += ","
            parts.append(",\n".join(fk_lines))

        parts.append(");")

        if table.description:
            parts.insert(0, f"-- {table.description}")

        return "\n".join(parts)

    @staticmethod
    def render_tables(tables: list[tuple[TableModel, list[ColumnModel]]]) -> dict[str, str]:
        return {t.name: DDLRenderer.render_table(t, cols) for t, cols in tables}


class QueryService:
    def __init__(
        self,
        vector_repo: VectorRepository,
        embedding_service: EmbeddingService | None = None,
        table_repo: TableRepository | None = None,
        column_repo: ColumnRepository | None = None,
    ) -> None:
        self._vector_repo = vector_repo
        self._embedding_service = embedding_service or EmbeddingService()
        self._table_repo = table_repo
        self._column_repo = column_repo

    async def search_context(
        self,
        question: str,
        tenant_id: str,
        limit: int = 10,
        score_threshold: float | None = None,
    ) -> dict[str, Any]:
        embedding = await self._embedding_service.embed_text(question)
        params = HybridSearchParams(
            query=question,
            content_type="schema_element",
            limit=limit,
            score_threshold=score_threshold,
        )
        results = await self._vector_repo.search_hybrid(
            tenant_id=tenant_id,
            dense_vector=embedding.dense_vector,
            sparse_vector=embedding.sparse_vector,
            params=params,
        )
        parsed = _parse_vector_results(results, tenant_id)

        enriched: dict[str, Any] = {}
        if self._table_repo and self._column_repo:
            enriched = await _enrich_with_ddl(
                parsed, self._table_repo, self._column_repo
            )

        return {
            "question": question,
            "tenant_id": tenant_id,
            "total_results": len(results),
            "tables": parsed.get("tables", []),
            "columns": parsed.get("columns", []),
            "relationships": parsed.get("relationships", []),
            "ddl_context": enriched.get("ddl_context", ""),
            "results": [
                {
                    "id": r.id,
                    "score": round(r.score, 4),
                    "content_type": r.payload.content_type,
                    "text": r.payload.text[:200] if r.payload.text else "",
                }
                for r in results
            ],
        }

    async def get_table_context(
        self,
        table_id: str,
        include_columns: bool = True,
        include_ddl: bool = True,
        include_relationships: bool = True,
    ) -> dict[str, Any] | None:
        if not self._table_repo or not self._column_repo:
            return None

        table = await self._table_repo.get(table_id)
        if table is None:
            return None

        result: dict[str, Any] = {
            "id": table.id,
            "name": table.name,
            "schema_id": table.schema_id,
            "description": table.description,
            "row_estimate": table.row_estimate,
            "is_active": table.is_active,
        }

        if include_columns or include_ddl:
            columns = await self._column_repo.list_by_table(table_id)
            cols_data = [
                {
                    "id": c.id,
                    "name": c.name,
                    "ordinal_position": c.ordinal_position,
                    "data_type": c.data_type,
                    "is_nullable": c.is_nullable,
                    "is_primary_key": c.is_primary_key,
                    "is_unique": c.is_unique,
                    "default_value": c.default_value,
                    "description": c.description,
                    "foreign_key_table": c.foreign_key_table,
                    "foreign_key_column": c.foreign_key_column,
                }
                for c in sorted(columns, key=lambda x: x.ordinal_position)
            ]
            if include_columns:
                result["columns"] = cols_data
            if include_ddl:
                result["ddl"] = DDLRenderer.render_table(table, columns)

        if include_relationships:
            result["relationships"] = []

        return result

    async def render_ddl(
        self, table_ids: list[str]
    ) -> dict[str, str]:
        if not self._table_repo or not self._column_repo:
            return {}

        result: dict[str, str] = {}
        for tid in table_ids:
            table = await self._table_repo.get(tid)
            if table is None:
                continue
            columns = await self._column_repo.list_by_table(tid)
            result[table.name] = DDLRenderer.render_table(table, columns)
        return result


def _parse_vector_results(
    results: list[SearchResult], tenant_id: str
) -> dict[str, list[dict[str, Any]]]:
    tables: list[dict[str, Any]] = []
    columns: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    seen_tables: set[str] = set()
    seen_columns: set[str] = set()
    seen_rels: set[str] = set()

    prefix = f"{tenant_id}:"
    for r in results:
        pid = r.id
        if pid.startswith(prefix):
            pid = pid[len(prefix):]
        text = r.payload.text or ""
        score = round(r.score, 4)

        if pid.startswith("table:"):
            tname = pid[len("table:"):]
            if tname not in seen_tables:
                seen_tables.add(tname)
                tables.append({"name": tname, "score": score, "text": text})
        elif pid.startswith("column:"):
            cname = pid[len("column:"):]
            if cname not in seen_columns:
                seen_columns.add(cname)
                parts = cname.split(".", 1)
                columns.append({
                    "name": cname,
                    "table": parts[0] if len(parts) == 2 else "",
                    "score": score,
                    "text": text,
                })
        elif pid.startswith("rel:"):
            rel_key = pid[len("rel:"):]
            if rel_key not in seen_rels:
                seen_rels.add(rel_key)
                relationships.append({"key": rel_key, "score": score, "text": text})

    return {
        "tables": tables,
        "columns": columns,
        "relationships": relationships,
    }


async def _enrich_with_ddl(
    parsed: dict[str, Any],
    table_repo: TableRepository,
    column_repo: ColumnRepository,
) -> dict[str, str]:
    ddl_lines: list[str] = []
    table_names = [t["name"] for t in parsed.get("tables", [])]
    col_tables: set[str] = set()
    for c in parsed.get("columns", []):
        if c["table"]:
            col_tables.add(c["table"])

    all_names = set(table_names) | col_tables
    rendered: set[str] = set()

    for tname in all_names:
        items, _ = await table_repo.list(filters={"name": tname, "is_active": True})
        for table in items:
            if table.name in rendered:
                continue
            rendered.add(table.name)
            columns = await column_repo.list_by_table(table.id)
            ddl = DDLRenderer.render_table(table, columns)
            ddl_lines.append(ddl)

    return {"ddl_context": "\n\n".join(ddl_lines)}
