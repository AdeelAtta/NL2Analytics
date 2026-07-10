from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConnectorConfig:
    host: str
    port: int
    database: str
    username: str
    password: str
    schema_filter: list[str] | None = None
    ssl: bool = True
    timeout_seconds: int = 30
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ForeignKeyRef:
    ref_table: str
    ref_column: str


@dataclass
class ExtractedColumn:
    name: str
    ordinal_position: int
    data_type: str
    is_nullable: bool
    is_primary_key: bool = False
    default_value: str | None = None
    foreign_key: ForeignKeyRef | None = None
    comment: str | None = None
    character_max_length: int | None = None
    numeric_precision: int | None = None
    numeric_scale: int | None = None


@dataclass
class ExtractedTable:
    name: str
    columns: list[ExtractedColumn]
    ddl: str = ""
    comment: str | None = None
    row_count_estimate: int | None = None


@dataclass
class ExtractedSchemaInfo:
    name: str
    tables: list[ExtractedTable]


@dataclass
class ExtractedSchema:
    database_name: str
    db_type: str
    schemas: list[ExtractedSchemaInfo]


class BaseConnector(ABC):
    @abstractmethod
    async def connect(self, config: ConnectorConfig) -> None:
        ...

    @abstractmethod
    async def extract_schemas(self) -> list[ExtractedSchemaInfo]:
        ...

    @abstractmethod
    async def extract_tables(self, schema_name: str) -> list[ExtractedTable]:
        ...

    @abstractmethod
    async def extract_columns(self, schema_name: str, table_name: str) -> list[ExtractedColumn]:
        ...

    @abstractmethod
    async def extract_relationships(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...

    async def __aenter__(self) -> BaseConnector:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()


class ConnectorRegistry:
    _connectors: dict[str, type[BaseConnector]] = {}

    @classmethod
    def register(cls, db_type: str, connector_cls: type[BaseConnector]) -> None:
        cls._connectors[db_type] = connector_cls

    @classmethod
    def get_connector(cls, db_type: str) -> type[BaseConnector]:
        if db_type not in cls._connectors:
            msg = f"No connector registered for db_type: {db_type}"
            raise KeyError(msg)
        return cls._connectors[db_type]

    @classmethod
    def list_types(cls) -> list[str]:
        return list(cls._connectors.keys())
