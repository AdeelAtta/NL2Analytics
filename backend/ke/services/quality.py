from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from ke.models.schema import Column as ColumnModel
from ke.models.schema import Table as TableModel
from ke.stores.schema.repository import ColumnRepository, TableRepository

logger = logging.getLogger(__name__)


class QualityScoreService:
    def __init__(
        self,
        table_repo: TableRepository,
        column_repo: ColumnRepository,
    ) -> None:
        self._table_repo = table_repo
        self._column_repo = column_repo

    async def score_tenant(self, tenant_id: str) -> dict[str, Any]:
        tables, total = await self._table_repo.list(filters={"is_active": True})

        if total == 0:
            return {
                "overall": 0.0,
                "dimensions": {
                    "coverage": 0.0,
                    "completeness": 0.0,
                    "consistency": 0.0,
                    "freshness": 0.0,
                },
                "details": {"total_tables": 0, "total_columns": 0},
            }

        all_columns: list[ColumnModel] = []
        for t in tables:
            cols = await self._column_repo.list_by_table(t.id)
            all_columns.extend(cols)

        coverage = _score_coverage(tables, all_columns)
        completeness = _score_completeness(tables, all_columns)
        consistency = _score_consistency(tables, all_columns)
        freshness = _score_freshness(tables)

        weights = {"coverage": 0.35, "completeness": 0.30, "consistency": 0.20, "freshness": 0.15}
        overall = sum(
            weights[k] * v for k, v in [("coverage", coverage), ("completeness", completeness), ("consistency", consistency), ("freshness", freshness)]
        )

        return {
            "overall": round(overall, 4),
            "dimensions": {
                "coverage": round(coverage, 4),
                "completeness": round(completeness, 4),
                "consistency": round(consistency, 4),
                "freshness": round(freshness, 4),
            },
            "details": {
                "total_tables": len(tables),
                "total_columns": len(all_columns),
                "tables_with_descriptions": sum(1 for t in tables if t.description),
                "columns_with_descriptions": sum(1 for c in all_columns if c.description),
                "described_table_pct": round(sum(1 for t in tables if t.description) / len(tables) * 100, 1) if tables else 0.0,
                "described_column_pct": round(sum(1 for c in all_columns if c.description) / len(all_columns) * 100, 1) if all_columns else 0.0,
            },
        }


def _score_coverage(tables: list[TableModel], columns: list[ColumnModel]) -> float:
    if not tables:
        return 0.0
    table_desc_ratio = sum(1 for t in tables if t.description) / len(tables)
    col_desc_ratio = sum(1 for c in columns if c.description) / len(columns) if columns else 0.0
    has_pk_ratio = sum(1 for t in tables if any(c.is_primary_key for c in columns if c.table_id == t.id)) / len(tables)
    return 0.4 * table_desc_ratio + 0.4 * col_desc_ratio + 0.2 * has_pk_ratio


def _score_completeness(tables: list[TableModel], columns: list[ColumnModel]) -> float:
    if not columns:
        return 0.0
    scored = 0
    total = 0
    for c in columns:
        total += 1
        s = 0.0
        if c.description:
            s += 0.4
            if len(c.description) > 20:
                s += 0.2
            if "." in c.description:
                s += 0.1
        if c.default_value is not None:
            s += 0.15
        if c.character_maximum_length is not None or c.numeric_precision is not None:
            s += 0.15
        scored += s
    return scored / total if total else 0.0


def _score_consistency(tables: list[TableModel], columns: list[ColumnModel]) -> float:
    if not columns:
        return 0.0
    lowercase_names = sum(1 for c in columns if c.name.islower())
    no_spaces = sum(1 for c in columns if " " not in c.name)
    has_standard_types = sum(
        1 for c in columns if c.data_type.lower() in {
            "integer", "bigint", "smallint", "varchar", "text", "boolean",
            "timestamp", "date", "numeric", "decimal", "float", "double",
            "uuid", "json", "jsonb", "serial", "bigserial",
        }
    )
    return (
        0.35 * (lowercase_names / len(columns))
        + 0.35 * (no_spaces / len(columns))
        + 0.30 * (has_standard_types / len(columns))
    )


def _score_freshness(tables: list[TableModel]) -> float:
    now = datetime.now(UTC)
    synced = [t.last_introspected_at for t in tables if t.last_introspected_at is not None]
    if not synced:
        return 0.0
    avg_age = sum((now - s).total_seconds() for s in synced) / len(synced)
    if avg_age < 3600:
        return 1.0
    if avg_age < 86400:
        return 0.8
    if avg_age < 604800:
        return 0.5
    if avg_age < 2592000:
        return 0.2
    return 0.0
