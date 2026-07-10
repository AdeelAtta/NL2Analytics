from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from schema_intelligence.connectors.base import ExtractedTable


@dataclass
class AnnotatedColumn:
    name: str
    description: str


@dataclass
class AnnotationResult:
    table_name: str
    table_description: str
    columns: list[AnnotatedColumn] = field(default_factory=list)


class BaseAnnotator(ABC):
    @abstractmethod
    async def annotate(self, table: ExtractedTable) -> AnnotationResult:
        ...

    @abstractmethod
    async def annotate_batch(
        self, tables: list[ExtractedTable]
    ) -> list[AnnotationResult]:
        ...
