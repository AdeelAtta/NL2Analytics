from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column as SAColumn
from sqlalchemy import DateTime, Integer, String, Text, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlglot import diff as sqlglot_diff
from sqlglot import parse_one

from ke.models.schema import (
    SchemaVersion as SchemaVersionModel,
)
from ke.stores.schema.repository import ORMBase


class SchemaVersionOrm(ORMBase):
    __tablename__ = "schema_versions"
    __table_args__ = {"schema": "schema_store"}

    id = SAColumn(PG_UUID(), primary_key=True, server_default=text("gen_random_uuid()"))
    schema_id = SAColumn(PG_UUID(), nullable=False)
    version = SAColumn(Integer(), nullable=False)
    changes = SAColumn(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    ddl_snapshot = SAColumn(Text, nullable=True)
    triggered_by = SAColumn(String(100), nullable=False, server_default="connector")
    created_at = SAColumn(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))


def _compute_ddl_hash(ddl: str) -> str:
    normalized = " ".join(ddl.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _classify_change(
    old_ddl: str | None, new_ddl: str
) -> list[dict[str, Any]]:
    if not old_ddl:
        return [{"change_type": "TABLE_ADDED", "object_name": "schema", "details": {}}]

    try:
        old_ast = parse_one(old_ddl)
        new_ast = parse_one(new_ddl)
    except Exception:
        return [
            {"change_type": "COLUMN_TYPE_CHANGED", "object_name": "unknown",
             "details": {"note": "DDL parse error"}},
        ]

    from sqlglot.diff import Insert, Remove

    diffs = sqlglot_diff(old_ast, new_ast)
    changes: list[dict[str, Any]] = []
    for d in diffs:
        if isinstance(d, Remove):
            name = _extract_name(d)
            changes.append({"change_type": "COLUMN_DROPPED", "object_name": name, "details": {}})
        elif isinstance(d, Insert):
            name = _extract_name(d)
            changes.append({"change_type": "COLUMN_ADDED", "object_name": name, "details": {}})
    if not changes:
        changes.append(
            {"change_type": "COLUMN_TYPE_CHANGED", "object_name": "column", "details": {}}
        )
    return changes


def _extract_name(d: Any) -> str:
    try:
        expr = d.expression if hasattr(d, "expression") else d
        return str(expr.args.get("this", expr)) if hasattr(expr, "args") else str(expr)
    except Exception:
        return "unknown"


class VersioningService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def detect_changes(
        self,
        schema_id: str,
        new_ddl: str,
        old_ddl: str | None = None,
        triggered_by: str = "connector",
    ) -> SchemaVersionModel:
        new_hash = _compute_ddl_hash(new_ddl)
        old_hash = _compute_ddl_hash(old_ddl) if old_ddl else None

        if old_hash == new_hash:
            changes: list[dict[str, Any]] = []
        else:
            changes = _classify_change(old_ddl, new_ddl)

        current_version = await self._get_current_version(schema_id)
        next_version = current_version + 1

        orm = SchemaVersionOrm(
            schema_id=schema_id,
            version=next_version,
            changes=changes,
            ddl_snapshot=new_ddl if changes else None,
            triggered_by=triggered_by,
            created_at=datetime.now(UTC),
        )
        self._session.add(orm)
        await self._session.flush()
        return SchemaVersionModel.model_validate(orm, from_attributes=True)

    async def _get_current_version(self, schema_id: str) -> int:
        stmt = (
            select(SchemaVersionOrm.version)
            .where(SchemaVersionOrm.schema_id == schema_id)
            .order_by(SchemaVersionOrm.version.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        current = result.scalar_one_or_none()
        return current or 0

    async def get_version_history(
        self, schema_id: str, limit: int = 50
    ) -> list[SchemaVersionModel]:
        stmt = (
            select(SchemaVersionOrm)
            .where(SchemaVersionOrm.schema_id == schema_id)
            .order_by(SchemaVersionOrm.version.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [
            SchemaVersionModel.model_validate(orm, from_attributes=True)
            for orm in result.scalars().all()
        ]

    async def get_version(
        self, schema_id: str, version: int
    ) -> SchemaVersionModel | None:
        stmt = select(SchemaVersionOrm).where(
            SchemaVersionOrm.schema_id == schema_id,
            SchemaVersionOrm.version == version,
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        return SchemaVersionModel.model_validate(orm, from_attributes=True)
