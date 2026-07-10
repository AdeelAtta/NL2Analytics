from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from schema_intelligence.annotators.base import AnnotationResult
from schema_intelligence.connectors.base import ExtractedSchemaInfo, ExtractedTable
from schema_intelligence.inference.base import InferredRelationship


class SyncChangeType(str, Enum):
    ADDED = "added"
    CHANGED = "changed"
    REMOVED = "removed"
    UNCHANGED = "unchanged"


@dataclass
class SyncChange:
    table: ExtractedTable
    change_type: SyncChangeType
    previous_signature: str | None = None
    current_signature: str | None = None
    annotation: AnnotationResult | None = None
    relationships: list[InferredRelationship] | None = None


@dataclass
class SyncState:
    signatures: dict[str, str] = field(default_factory=dict)
    last_synced_at: datetime | None = None


@dataclass
class SyncResult:
    schema_info: ExtractedSchemaInfo
    changes: list[SyncChange] = field(default_factory=list)
    synced_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    errors: list[str] = field(default_factory=list)

    @property
    def added_count(self) -> int:
        return sum(1 for c in self.changes if c.change_type == SyncChangeType.ADDED)

    @property
    def changed_count(self) -> int:
        return sum(1 for c in self.changes if c.change_type == SyncChangeType.CHANGED)

    @property
    def removed_count(self) -> int:
        return sum(1 for c in self.changes if c.change_type == SyncChangeType.REMOVED)

    @property
    def unchanged_count(self) -> int:
        return sum(1 for c in self.changes if c.change_type == SyncChangeType.UNCHANGED)


def table_signature(table: ExtractedTable) -> str:
    if table.ddl:
        normalized = " ".join(table.ddl.split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    parts: list[str] = []
    for col in sorted(table.columns, key=lambda c: c.ordinal_position):
        fk_str = (
            f"{col.foreign_key.ref_table}.{col.foreign_key.ref_column}"
            if col.foreign_key
            else ""
        )
        parts.append(
            f"{col.name}:{col.data_type}:{col.is_nullable}:{col.is_primary_key}:{col.default_value or ''}:{fk_str}"
        )
    raw = ";".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
