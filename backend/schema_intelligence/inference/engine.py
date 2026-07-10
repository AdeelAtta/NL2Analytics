from __future__ import annotations

from schema_intelligence.connectors.base import ExtractedTable
from schema_intelligence.inference.base import (
    InferenceContext,
    InferredRelationship,
)
from schema_intelligence.inference.name_based import NameBasedInferenceEngine


class RelationshipInferenceService:
    def __init__(
        self,
        min_confidence: float = 0.3,
        naming_confidence: float = 0.7,
        reverse_naming_confidence: float = 0.5,
        overlap_confidence: float = 0.3,
        junction_confidence: float = 0.8,
        self_reference_threshold: float = 0.9,
        score_fusion_bonus: float = 0.2,
    ) -> None:
        self._engine = NameBasedInferenceEngine()
        self._min_confidence = min_confidence
        self._naming_confidence = naming_confidence
        self._reverse_naming_confidence = reverse_naming_confidence
        self._overlap_confidence = overlap_confidence
        self._junction_confidence = junction_confidence
        self._self_reference_threshold = self_reference_threshold
        self._score_fusion_bonus = score_fusion_bonus

    def infer(self, tables: list[ExtractedTable]) -> list[InferredRelationship]:
        context = InferenceContext(
            tables=tables,
            self_reference_threshold=self._self_reference_threshold,
            naming_confidence=self._naming_confidence,
            reverse_naming_confidence=self._reverse_naming_confidence,
            overlap_confidence=self._overlap_confidence,
            junction_confidence=self._junction_confidence,
            score_fusion_bonus=self._score_fusion_bonus,
            min_confidence=self._min_confidence,
        )
        return self._engine.infer(context)
