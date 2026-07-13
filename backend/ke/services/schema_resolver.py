from __future__ import annotations

from typing import Any

from ke.models.planning import QueryIntent
from ke.stores.schema.repository import ColumnRepository, RelationshipRepository, TableRepository


class SchemaResolver:
    def __init__(
        self,
        table_repo: TableRepository | None = None,
        column_repo: ColumnRepository | None = None,
        rel_repo: RelationshipRepository | None = None,
    ) -> None:
        self._table_repo = table_repo
        self._column_repo = column_repo
        self._rel_repo = rel_repo

    async def resolve(
        self,
        intent: QueryIntent,
        tenant_id: str = "default",
        question: str = "",
    ) -> dict[str, Any]:
        context: dict[str, Any] = {
            "tables": [],
            "columns": [],
            "relationships": [],
            "ddl_context": "",
        }

        table_names = [t.name.lower() for t in intent.tables if t.name]

        if not table_names:
            return context

        resolved_tables = await self._resolve_tables(table_names, tenant_id)
        if not resolved_tables:
            return context

        table_ids = [t["id"] for t in resolved_tables]
        id_to_name = {t["id"]: t["name"] for t in resolved_tables if t["id"]}

        all_columns: list[dict[str, Any]] = []
        for table_id in table_ids:
            cols = await self._resolve_columns(table_id)
            for col in cols:
                tid = col.get("table_id", "")
                col["table_name"] = id_to_name.get(tid, col.get("table_name", tid))
            all_columns.extend(cols)

        relationships = await self._resolve_relationships(table_ids, tenant_id)

        context["tables"] = resolved_tables
        context["columns"] = all_columns
        context["relationships"] = relationships

        ddl_lines: list[str] = []
        for tbl in resolved_tables:
            tbl_name = tbl["name"]
            tbl_cols = [c for c in all_columns if c.get("table_name", "").lower() == tbl_name.lower()]
            ddl_lines.append(f"CREATE TABLE {tbl_name} (")
            for col in tbl_cols:
                parts = [f"  {col['name']} {col['data_type']}"]
                if col.get("is_primary_key"):
                    parts.append("PK")
                if not col.get("is_nullable", True):
                    parts.append("NOT NULL")
                ddl_lines.append(" ".join(parts))
            ddl_lines.append(");")
            for rel in relationships:
                src = rel.get("source_table", "")
                tgt = rel.get("target_table", "")
                if src.lower() == tbl_name.lower() or tgt.lower() == tbl_name.lower():
                    src_col = rel.get("source_column", "id")
                    tgt_col = rel.get("target_column", "id")
                    ddl_lines.append(f"-- {src}.{src_col} -> {tgt}.{tgt_col}")
        context["ddl_context"] = "\n".join(ddl_lines)

        return context

    async def _resolve_tables(self, table_names: list[str], tenant_id: str) -> list[dict[str, Any]]:
        if not self._table_repo:
            return [{"id": "", "name": name, "schema_name": "", "description": ""} for name in table_names]
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for name in table_names:
            if name in seen:
                continue
            seen.add(name)
            items, _ = await self._table_repo.list(filters={"name": name, "is_active": True})
            if items:
                tbl = items[0]
                results.append({
                    "id": tbl.id,
                    "name": tbl.name,
                    "schema_name": getattr(tbl, "schema_name", ""),
                    "description": tbl.description or "",
                    "row_estimate": getattr(tbl, "row_estimate", 0),
                })
            else:
                results.append({"id": "", "name": name, "schema_name": "", "description": ""})
        return results

    async def _resolve_columns(self, table_id: str) -> list[dict[str, Any]]:
        if not self._column_repo or not table_id:
            return []
        try:
            cols = await self._column_repo.list_by_table(table_id)
            return [
                {
                    "table_id": col.table_id,
                    "table_name": col.table_id,
                    "name": col.name,
                    "data_type": col.data_type,
                    "is_nullable": col.is_nullable,
                    "is_primary_key": col.is_primary_key,
                    "ordinal_position": col.ordinal_position,
                }
                for col in cols
            ]
        except Exception:
            return []

    async def _resolve_relationships(
        self, table_ids: list[str], tenant_id: str
    ) -> list[dict[str, Any]]:
        if not self._rel_repo:
            return []
        try:
            rels: list[dict[str, Any]] = []
            for tid in table_ids:
                src_rels = await self._rel_repo.list_by_source_table(tid)
                for r in src_rels:
                    rels.append({
                        "source_table": getattr(r, "source_table_name", r.source_table_id),
                        "source_column": r.source_column,
                        "target_table": getattr(r, "target_table_name", r.target_table_id),
                        "target_column": r.target_column,
                        "relationship_type": r.relationship_type,
                    })
                tgt_rels = await self._rel_repo.list_by_target_table(tid)
                for r in tgt_rels:
                    rels.append({
                        "source_table": getattr(r, "source_table_name", r.source_table_id),
                        "source_column": r.source_column,
                        "target_table": getattr(r, "target_table_name", r.target_table_id),
                        "target_column": r.target_column,
                        "relationship_type": r.relationship_type,
                    })
            return rels
        except Exception:
            return []


