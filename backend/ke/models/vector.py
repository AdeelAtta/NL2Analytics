from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field
from pydantic.functional_validators import BeforeValidator

from shared.models.base import BaseSchema, TenantScopedModel

UUIDStr = Annotated[
    str,
    BeforeValidator(lambda v: str(v) if not isinstance(v, str) else v),
]


class SparseVector(BaseSchema):
    indices: list[int]
    values: list[float]


class EmbeddingResult(BaseSchema):
    id: str
    dense_vector: list[float]
    sparse_vector: SparseVector | None = None
    embedding_model: str = "BAAI/bge-m3"
    dimension: int = 1024
    normalized: bool = True


class EmbeddingRequest(BaseSchema):
    items: list[EmbeddingItem]
    model: str = "BAAI/bge-m3"
    batch_size: int = 100


class EmbeddingItem(BaseSchema):
    id: str
    text: str
    content_type: Literal["schema_element", "query_pattern", "business_term"] = "schema_element"
    source_id: str


class VectorPoint(BaseSchema):
    id: str
    dense_vector: list[float]
    sparse_vector: SparseVector | None = None
    payload: VectorPayload


class VectorPayload(TenantScopedModel):
    content_type: Literal["schema_element", "query_pattern", "business_term"] = "schema_element"
    source_id: str
    text: str
    embedding_model: str = "BAAI/bge-m3"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class SearchResult(BaseSchema):
    id: str
    score: float
    payload: VectorPayload
    dense_score: float | None = None
    sparse_score: float | None = None


class HybridSearchParams(BaseSchema):
    query: str
    content_type: Literal["schema_element", "query_pattern", "business_term"] | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    dense_weight: float = Field(default=0.7, ge=0.0, le=1.0)
    score_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    tenant_id: str | None = None
