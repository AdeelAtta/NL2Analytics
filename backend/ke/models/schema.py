from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator
from pydantic.functional_validators import BeforeValidator

from shared.models.base import BaseSchema

UUIDStr = Annotated[
    str,
    BeforeValidator(lambda v: str(v) if not isinstance(v, str) else v),
]


def _validate_slug(v: str) -> str:
    if not re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", v):
        msg = f"Slug must match pattern ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$, got {v!r}"
        raise ValueError(msg)
    return v


class Tenant(BaseSchema):
    model_config = {"from_attributes": True}

    id: UUIDStr
    name: str
    slug: Annotated[str, BeforeValidator(_validate_slug)]
    tier: Literal["free", "starter", "pro", "enterprise"] = "starter"
    status: Literal["active", "suspended", "deleting", "deleted"] = "active"
    settings: dict[str, Any] = Field(default_factory=dict)
    features: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class DatabaseConfig(BaseSchema):
    model_config = {"from_attributes": True}

    id: UUIDStr
    tenant_id: UUIDStr
    name: str
    db_type: Literal["postgresql", "mysql", "snowflake", "bigquery", "duckdb"]
    connection_hash: str
    host: str | None = None
    port: int | None = None
    database_name: str | None = None
    username: str | None = None
    schema_filter: list[str] | None = None
    ssl_enabled: bool = True
    connection_options: dict[str, Any] = Field(default_factory=dict)
    sync_status: Literal["pending", "syncing", "synced", "error"] = "pending"
    sync_error_message: str | None = None
    last_synced_at: datetime | None = None
    table_count: int = 0
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class SchemaInfo(BaseSchema):
    model_config = {"from_attributes": True}

    id: UUIDStr
    database_id: UUIDStr
    name: str
    raw_ddl: str | None = None
    version: int = 1
    table_count: int = 0
    created_at: datetime
    updated_at: datetime


class Table(BaseSchema):
    model_config = {"from_attributes": True}

    id: UUIDStr
    schema_id: UUIDStr
    name: str
    description: str | None = None
    ddl: str | None = None
    row_estimate: int = 0
    version: int = 1
    is_active: bool = True
    last_introspected_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class Column(BaseSchema):
    model_config = {"from_attributes": True}

    id: UUIDStr
    table_id: UUIDStr
    name: str
    ordinal_position: int
    data_type: str
    is_nullable: bool = True
    is_primary_key: bool = False
    is_unique: bool = False
    default_value: str | None = None
    description: str | None = None
    foreign_key_table: str | None = None
    foreign_key_column: str | None = None
    character_maximum_length: int | None = None
    numeric_precision: int | None = None
    numeric_scale: int | None = None
    created_at: datetime
    updated_at: datetime


class Relationship(BaseSchema):
    model_config = {"from_attributes": True}

    id: UUIDStr
    tenant_id: UUIDStr
    source_table_id: UUIDStr
    source_column: str
    target_table_id: UUIDStr
    target_column: str
    relationship_type: Literal["foreign_key", "inferred", "semantic"] = "foreign_key"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    discovered_by: Literal["connector", "inferer", "llm", "manual"] = "connector"
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    @field_validator("confidence")
    @classmethod
    def _check_confidence(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            msg = f"Confidence must be between 0.0 and 1.0, got {v}"
            raise ValueError(msg)
        return v


class SchemaChangeType(str, Enum):
    TABLE_ADDED = "TABLE_ADDED"
    TABLE_DROPPED = "TABLE_DROPPED"
    COLUMN_ADDED = "COLUMN_ADDED"
    COLUMN_DROPPED = "COLUMN_DROPPED"
    COLUMN_RENAMED = "COLUMN_RENAMED"
    COLUMN_TYPE_CHANGED = "COLUMN_TYPE_CHANGED"
    COLUMN_NULLABLE_CHANGED = "COLUMN_NULLABLE_CHANGED"
    RELATIONSHIP_ADDED = "RELATIONSHIP_ADDED"
    RELATIONSHIP_DROPPED = "RELATIONSHIP_DROPPED"


class SchemaChange(BaseSchema):
    change_type: SchemaChangeType
    object_name: str
    details: dict[str, Any] = Field(default_factory=dict)


class SchemaVersion(BaseSchema):
    model_config = {"from_attributes": True}

    id: UUIDStr
    schema_id: UUIDStr
    version: int
    changes: list[SchemaChange] = Field(default_factory=list)
    ddl_snapshot: str | None = None
    triggered_by: str = "connector"
    created_at: datetime
