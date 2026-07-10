from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from schema_intelligence.connectors.base import ExtractedTable


@dataclass
class InferredRelationship:
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    confidence: float = 1.0
    strategy: str = "unknown"
    relationship_type: str = "inferred"


@dataclass
class InferenceContext:
    tables: list[ExtractedTable]
    self_reference_threshold: float = 0.9
    naming_confidence: float = 0.7
    reverse_naming_confidence: float = 0.5
    overlap_confidence: float = 0.3
    junction_confidence: float = 0.8
    score_fusion_bonus: float = 0.2
    min_confidence: float = 0.3


class BaseInferenceEngine(ABC):
    @abstractmethod
    def infer(self, context: InferenceContext) -> list[InferredRelationship]:
        ...
